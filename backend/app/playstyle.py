"""Session 14 — the playstyle index (tactical ↔ positional).

Session 12 produced aggregate rates (blunders/game, ACPL, conversion) and
Session 13 named specific patterns (hung pieces, late collapse, etc.). This
module adds a single, explainable style dimension: how positional or
tactical a player's games are, based purely on already-stored move_evals.

The formula is fixed in Appendix 5 of the roadmap and is NOT configuration.
That is why the bounds and weights live here as a documented module-level
table, not in app/config.py. If the formula's verdict ever feels wrong, the
correct fix is to amend Appendix 5 first, then mirror that change here.
Never silently drift from the appendix.

Every computation below is PURE: it takes only (games, evals) and has no
engine, network, or database access. Every stored eval is White-POV. The
only sanctioned conversion to the player's POV is player_pov_eval() from
app/analysis (Cardinal Rule 7).

Operationalization notes (spec underspecifications made explicit here so
Appendix 5 can be tuned before the code if the verdict is wrong):

- eval_volatility uses eval_cp_after (the eval AFTER each move), pooled
  over all plies of all games, and converted to the player's POV.
- queen_keep checks whether at least one queen is still on the board at the
  ply-30 boundary (the first position with ply > 30, read from fen_before).
- opposite_castling requires BOTH sides to have castled and to be on
  opposite wings (kingside vs queenside).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.analysis import is_player_ply, player_pov_eval
from app.models import Game, MoveEval


# ---------------------------------------------------------------------------
# Appendix 5 formula constants (bounds + weights)
#
# For each component the raw metric is clamped between lo and hi, then
# linearly rescaled so lo -> -1 (positional) and hi -> +1 (tactical).
# game_length is INVERTED: shorter games are more tactical, so lo=90 plies
# (positional / long) and hi=40 plies (tactical / short).
# ---------------------------------------------------------------------------

_COMPONENTS = {
    "capture_density": {"lo": 0.15, "hi": 0.40, "weight": 0.25},
    "game_length": {"lo": 90, "hi": 40, "weight": 0.15},
    "eval_volatility": {"lo": 60, "hi": 250, "weight": 0.25},
    "opposite_castling": {"lo": 0.00, "hi": 0.30, "weight": 0.20},
    "queen_keep": {"lo": 0.35, "hi": 0.75, "weight": 0.15},
}

_WEIGHTS = {name: spec["weight"] for name, spec in _COMPONENTS.items()}


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


@dataclass
class Playstyle:
    """The playstyle index result: a label, a single score in [-1, +1],
    a plain-language explanation, and the per-component normalized values
    (useful for debug UI)."""

    label: str
    score: float
    explanation: str
    components: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------


def _normalize(raw: float, lo: float, hi: float) -> float:
    """Clamp raw to [min(lo, hi), max(lo, hi)], then linearly rescale so
    lo maps to -1 and hi maps to +1.

    This is the same linear map for every component; the only special case
    is game_length, where lo=90 and hi=40 (inverted). The formula still
    holds: a 90-ply game scores -1 (positional), a 40-ply game scores +1
    (tactical), and 65 plies lands at ~0.
    """
    lower, upper = min(lo, hi), max(lo, hi)
    clamped = max(lower, min(raw, upper))
    return 2 * (clamped - lo) / (hi - lo) - 1


# ---------------------------------------------------------------------------
# Raw component functions
# ---------------------------------------------------------------------------


def _capture_density(games: list[Game], evals: dict[str, list[MoveEval]]) -> float:
    """Player captures divided by player moves.

    A 'player move' is a move_evals row whose ply belongs to the player
    (is_player_ply). A 'capture' is such a row whose SAN contains 'x'.
    Returns 0.0 when the player has zero moves across all games.
    """
    player_moves = 0
    captures = 0
    for game in games:
        for row in evals.get(str(game.id), []):
            if not is_player_ply(row.ply, game.player_color):
                continue
            player_moves += 1
            if "x" in row.move_san:
                captures += 1
    return captures / player_moves if player_moves else 0.0


def _game_length(games: list[Game], evals: dict[str, list[MoveEval]]) -> float:
    """Mean number of plies (move_evals rows) per game.

    Shorter games skew toward the tactical end in the final score because
    Appendix 5 inverts this metric: lo=90 plies is positional, hi=40 plies
    is tactical.
    """
    if not games:
        return 0.0
    total = sum(len(evals.get(str(game.id), [])) for game in games)
    return total / len(games)


def _eval_volatility(games: list[Game], evals: dict[str, list[MoveEval]]) -> float:
    """Population standard deviation of the player's POV eval across every
    recorded ply of every game (both movers - this reads POSITION, not the
    mover's cp_loss). Uses eval_cp_after as the operationalized volatility
    read (operationalization note: this is the eval AFTER each move).

    The player's POV is obtained via player_pov_eval(row.eval_cp_after,
    game.player_color). Returns 0.0 when there are fewer than 2 data points,
    because a standard deviation with zero or one points is undefined.
    """
    values: list[float] = []
    for game in games:
        for row in evals.get(str(game.id), []):
            values.append(player_pov_eval(row.eval_cp_after, game.player_color))

    n = len(values)
    if n < 2:
        return 0.0

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def _opposite_castling(games: list[Game], evals: dict[str, list[MoveEval]]) -> float:
    """Share of games where both sides castled AND on opposite wings.

    Castling is detected from stored move_san: 'O-O' or 'O-O-O' on an odd
    ply is a White castle; on an even ply is a Black castle. Opposite-wing
    means one side castled kingside and the other queenside. BOTH sides must
    have castled (operationalization note: this requires both a White and a
    Black castle). Games where one side (or both) did not castle contribute 0
    to the numerator. Denominator is every game passed in.
    """
    if not games:
        return 0.0

    opposite = 0
    for game in games:
        white_castle: str | None = None
        black_castle: str | None = None
        for row in evals.get(str(game.id), []):
            if row.move_san in ("O-O", "O-O-O"):
                if row.ply % 2 == 1:
                    white_castle = row.move_san
                else:
                    black_castle = row.move_san

        if white_castle is not None and black_castle is not None:
            if (white_castle == "O-O" and black_castle == "O-O-O") or (
                white_castle == "O-O-O" and black_castle == "O-O"
            ):
                opposite += 1

    return opposite / len(games)


def _queen_keep(games: list[Game], evals: dict[str, list[MoveEval]]) -> float:
    """Share of games where at least one queen is still on the board past
    the ply-30 boundary.

    Reads the position from fen_before of the FIRST move_evals row with
    ply > 30 (the position after 30 plies have been played). 'At least one
    queen present' is the operationalized test (operationalization note:
    queen_keep = at least one queen present at the ply-30 boundary). A game
    that ended by ply 30 does NOT qualify as a 'keep' - there is no such
    row, so it contributes 0 to the numerator. Denominator is every game
    passed in.
    """
    if not games:
        return 0.0

    kept = 0
    for game in games:
        rows = evals.get(str(game.id), [])
        boundary = next((r for r in rows if r.ply > 30), None)
        if boundary is not None:
            placement = boundary.fen_before.split(" ")[0]
            if "Q" in placement or "q" in placement:
                kept += 1

    return kept / len(games)


# ---------------------------------------------------------------------------
# Explanations: plain-language fragments for each component
# ---------------------------------------------------------------------------


def _component_sentence(name: str, raw: float, normalized: float) -> str:
    """A short human clause for the explanation, interpolating the raw
    metric. The goal is a sentence the founder can read and sanity-check."""
    if name == "capture_density":
        pct = raw * 100
        return f"you trade or take pieces on {pct:.0f}% of your moves"
    if name == "game_length":
        return f"your games run about {raw:.0f} plies long"
    if name == "eval_volatility":
        return f"your evals swing by about {raw:.0f} centipawns on average"
    if name == "opposite_castling":
        return f"you castle opposite sides in {raw*100:.0f}% of games"
    if name == "queen_keep":
        return f"queens stay on the board past ply 30 in {raw*100:.0f}% of your games"
    return f"{name} is {raw}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_playstyle(games: list[Game], evals: dict[str, list[MoveEval]]) -> Playstyle:
    """Compute the Appendix 5 playstyle index from already-stored games and
    move_evals.

    The result is one score in [-1, +1], a label, and a plain-language
    explanation. A positive score means more tactical; a negative score
    means more positional. The explanation highlights the two components
    whose normalized values have the largest absolute magnitude, because
    those are the components most responsible for pushing the verdict one
    way or the other.

    Degenerate / empty input guard: when there are no games, or when the
    player has zero moves (so capture_density's denominator is empty), the
    function returns a neutral 'balanced' result with all components at 0.0.
    """
    if not games:
        return _neutral_playstyle()

    # Also guard the case where the player simply never moved (0 player
    # moves). capture_density would divide by zero, and the other metrics
    # would also be meaningless.
    total_player_moves = sum(
        1
        for game in games
        for row in evals.get(str(game.id), [])
        if is_player_ply(row.ply, game.player_color)
    )
    if total_player_moves == 0:
        return _neutral_playstyle()

    raw_metrics = {
        "capture_density": _capture_density(games, evals),
        "game_length": _game_length(games, evals),
        "eval_volatility": _eval_volatility(games, evals),
        "opposite_castling": _opposite_castling(games, evals),
        "queen_keep": _queen_keep(games, evals),
    }

    normalized: dict[str, float] = {}
    for name, raw in raw_metrics.items():
        spec = _COMPONENTS[name]
        normalized[name] = _normalize(raw, spec["lo"], spec["hi"])

    score = round(sum(normalized[name] * _WEIGHTS[name] for name in normalized), 2)

    if score <= -0.25:
        label = "positional"
    elif score >= 0.25:
        label = "tactical"
    else:
        label = "balanced"

    explanation = _build_explanation(raw_metrics, normalized)

    return Playstyle(
        label=label,
        score=score,
        explanation=explanation,
        components={name: round(v, 2) for name, v in normalized.items()},
    )


def _build_explanation(raw_metrics: dict[str, float], normalized: dict[str, float]) -> str:
    """Cite the two components with the largest |normalized| values, using
    their raw numbers in plain language."""
    top_two = sorted(normalized, key=lambda name: abs(normalized[name]), reverse=True)[:2]
    clauses = [_component_sentence(name, raw_metrics[name], normalized[name]) for name in top_two]
    return f"{clauses[0]} and {clauses[1]} - that is the biggest driver of your style."


def _neutral_playstyle() -> Playstyle:
    """Degenerate-input result: balanced with all components at 0.0."""
    return Playstyle(
        label="balanced",
        score=0.0,
        explanation="Not enough games yet to pin down a playstyle.",
        components={name: 0.0 for name in _COMPONENTS},
    )
