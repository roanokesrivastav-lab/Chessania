"""Session 12 — the first aggregation layer over analyzed games.

Session 9 turned raw engine evals into per-move labels (ok/inaccuracy/mistake/
blunder/skipped, opening/middlegame/endgame). Those move_evals rows are ground
truth, but nobody wants to read 2,000 individual ply rows — a coach speaks in
numbers like "you lose 1.4 pawns a game" and "your endgames fall apart", and
this module is where the raw rows become those numbers.

Everything below is PURE aggregation: no engine, no network, no DB access
except in the one thin loader at the bottom (`load_features`). That split
mirrors analysis.py's own split (pure helpers vs. the DB-touching
`analyze_game`) and for the same reason — pure functions are the ones you can
pin down with hand-computed numbers in a fast offline test.

Evidence discipline (roadmap Locked Decision 8, "every coaching string must
contain the player's numbers"): every rate or average below is paired with a
short evidence list — up to 3 `(game_id, ply)` pairs pointing at the actual
moves that produced it — so a downstream coaching sentence can always cite a
real game instead of asserting a vibe.

Perspective: every stored eval is White's POV (Cardinal Rule 7). The only two
sanctioned conversions in the whole codebase are `cp_loss()` (analysis.py,
S9) and `player_pov_eval()` (analysis.py, S12) — this module calls the
latter wherever it needs "how good is this position FOR the player" (opening
leak, endgame conversion) and never flips a sign itself.

Layering ahead: this module (`PlayerFeatures`) is the raw numbers. Session 13
adds `detectors` (pattern-matching over these numbers into named weaknesses,
e.g. "hangs pieces in time trouble") — the field is reserved here as
`detectors: dict | None = None` so the shape is stable before that code
exists. Session 14 adds playstyle (tactical/positional/balanced) as its own
separate computation, not part of this dataclass.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import is_player_ply, player_pov_eval
from app.config import settings
from app.detectors import run_detectors
from app.models import Game, MoveEval, Player
from app.playstyle import Playstyle, compute_playstyle

_PHASES = ("opening", "middlegame", "endgame")


# ---------------------------------------------------------------------------
# Dataclasses — the full shape now; later-session sections (detectors) are None.
# ---------------------------------------------------------------------------


@dataclass
class WLD:
    """Win/loss/draw tally, from `games.result`."""

    win: int = 0
    loss: int = 0
    draw: int = 0


@dataclass
class PhaseACPL:
    """Average centipawn loss per phase. None = no non-skipped moves in that
    phase (not 0.0 — "no data" and "played it perfectly" must never look the
    same to the coach)."""

    opening: float | None = None
    middlegame: float | None = None
    endgame: float | None = None


@dataclass
class ColorStats:
    """The same weakness numbers as PlayerFeatures, recomputed over just one
    color's games — mirrors roadmap Appendix 2's ColorStats exactly, so a real
    white-vs-black gap is a first-class reportable weakness instead of being
    averaged away (2026-07-25 amendment)."""

    games: int
    results: WLD
    blunders_per_game: float
    acpl_overall: float | None
    acpl_by_phase: PhaseACPL
    worst_phase: str | None
    opening_leak_rate: float
    endgame_conversion: float | None
    low_signal: bool  # < FEATURE_COLOR_MIN_GAMES of this color -> coach copy must hedge


@dataclass
class PlayerFeatures:
    """The numbers the coach speaks in. One of these per player, built fresh
    from whatever games are currently analyzed (no caching — recomputing this
    is cheap; only the engine pass in analyze_game is expensive)."""

    games_analyzed: int
    results: WLD
    rating_snapshot: int | None
    time_class_mix: dict[str, int]  # keys "blitz"/"rapid", only classes actually played

    blunders_per_game: float
    mistakes_per_game: float
    inaccuracies_per_game: float

    acpl_overall: float | None
    acpl_by_phase: PhaseACPL
    worst_phase: str | None
    worst_phase_margin: float | None
    worst_phase_evidence: list[tuple[str, int]]

    accuracy_trend: str  # improving | flat | declining | insufficient_data
    per_game_acpl: list[float]  # chronological, for any future sparkline

    opening_leak_rate: float
    opening_leak_evidence: list[tuple[str, int]]

    endgame_conversion: float | None
    endgame_conversion_evidence: list[tuple[str, int]]

    # S13: the blunder-inflation resolution. blunders_per_game (above) counts
    # every player blunder in every game, including ones played after a lost
    # game's point-of-no-return (PONR) — moves in an already-decided game that
    # are noise, not a real accuracy signal. This counts only PLAYER blunders
    # at or before that game's PONR (turning_point detector's ponr_by_game);
    # games with no PONR count all their player blunders. blunders_per_game
    # itself is left unchanged so nothing that already reads it drifts.
    meaningful_blunders_per_game: float = 0.0

    by_color: dict[str, ColorStats] = field(default_factory=dict)  # only colors actually played

    detectors: dict | None = None  # S13: pattern-matched named weaknesses (see app/detectors.py)
    playstyle: Playstyle | None = None  # S14: tactical/positional/balanced index (see app/playstyle.py)
    top_eco_by_color: dict[str, str | None] = field(default_factory=dict)  # S16: most-frequent ECO per color


# ---------------------------------------------------------------------------
# Small rounding helper — keep internal math float, round only where a value
# is about to land in a dataclass field (the "boundary" the roadmap wants).
# ---------------------------------------------------------------------------


def _round1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


# ---------------------------------------------------------------------------
# Pure core helpers
# ---------------------------------------------------------------------------


def _wld(games: list[Game]) -> WLD:
    """Tally win/loss/draw straight from games.result."""
    wld = WLD()
    for g in games:
        if g.result == "win":
            wld.win += 1
        elif g.result == "loss":
            wld.loss += 1
        elif g.result == "draw":
            wld.draw += 1
    return wld


def _class_counts(rows: list[MoveEval]) -> dict[str, int]:
    """How many rows fall in each classification bucket."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.classification] = counts.get(row.classification, 0) + 1
    return counts


def _acpl(rows: list[MoveEval]) -> float | None:
    """Mean cp_loss over non-skipped rows. 'skipped' rows are excluded on
    purpose: they're moves played in an already-decided (crushing/crushed)
    position, and models.py's own law is that counting them "would poison
    every rate computed downstream" — a single 'blunder' in a position that
    was already +900 is noise, not a data point about the player's accuracy.
    None (not 0.0) when there are zero non-skipped rows to average — "no
    data" must never look like "played perfectly"."""
    losses = [r.cp_loss for r in rows if r.classification != "skipped"]
    if not losses:
        return None
    return sum(losses) / len(losses)


def _acpl_by_phase(rows: list[MoveEval]) -> PhaseACPL:
    """ACPL, split per phase. Each phase reuses `_acpl` over just that
    phase's non-skipped rows."""
    return PhaseACPL(
        opening=_round1(_acpl([r for r in rows if r.phase == "opening"])),
        middlegame=_round1(_acpl([r for r in rows if r.phase == "middlegame"])),
        endgame=_round1(_acpl([r for r in rows if r.phase == "endgame"])),
    )


def _worst_phase(by_phase: PhaseACPL, overall: float | None) -> tuple[str | None, float | None]:
    """Which phase is the player's own weakest, self-referenced against their
    OWN overall ACPL (per the roadmap: compare the player to themselves, not
    to some external bar). Only a phase whose ACPL actually EXCEEDS overall
    (phase_acpl - overall > 0) counts as "worse" — if no phase exceeds
    overall (or there's no overall to compare against), there is no single
    worst phase and both return values are None."""
    if overall is None:
        return None, None

    candidates: list[tuple[str, float]] = []
    for phase in _PHASES:
        value = getattr(by_phase, phase)
        if value is None:
            continue
        margin = round(value - overall, 1)
        if margin > 0:
            candidates.append((phase, margin))

    if not candidates:
        return None, None
    return max(candidates, key=lambda pair: pair[1])


def _worst_phase_evidence(
    games: list[Game], evals: dict[str, list[MoveEval]], worst_phase: str | None
) -> list[tuple[str, int]]:
    """Up to 3 (game_id, ply) citations backing up 'worst_phase' — the
    individual moves with the highest cp_loss inside that phase, across every
    analyzed game. This is what lets a coaching sentence about the worst
    phase point at real moves instead of just naming a phase.

    `evals` here is expected to already be player-filtered (build_features
    passes `player_evals`, not the raw evals dict) — worst_phase itself is
    now a PER-MOVER stat (S13), so its evidence must cite the player's own
    moves, never the opponent's."""
    if worst_phase is None:
        return []

    candidates: list[tuple[str, int, int]] = []
    for game in games:
        for row in evals.get(str(game.id), []):
            if row.phase == worst_phase and row.classification != "skipped":
                candidates.append((str(game.id), row.ply, row.cp_loss))

    candidates.sort(key=lambda c: c[2], reverse=True)
    return [(game_id, ply) for game_id, ply, _cp_loss in candidates[:3]]


def _accuracy_trend(per_game_acpl: list[float]) -> str:
    """Compare the first half of the (chronological) per-game ACPL list to
    the second half. Lower ACPL is BETTER, so a second half that's
    meaningfully LOWER than the first is "improving"; meaningfully HIGHER is
    "declining"; within FEATURE_TREND_BAND of each other is "flat". Fewer than
    FEATURE_TREND_MIN_GAMES games isn't enough signal to call a trend at
    all."""
    if len(per_game_acpl) < settings.FEATURE_TREND_MIN_GAMES:
        return "insufficient_data"

    mid = len(per_game_acpl) // 2
    first_half = per_game_acpl[:mid]
    second_half = per_game_acpl[mid:]
    f = sum(first_half) / len(first_half)
    s = sum(second_half) / len(second_half)

    if f == 0:
        return "flat"

    band = settings.FEATURE_TREND_BAND
    if s < f * (1 - band):
        return "improving"
    if s > f * (1 + band):
        return "declining"
    return "flat"


def _opening_leak_pov_eval(game: Game, rows: list[MoveEval]) -> int | None:
    """Player-POV eval read at the opening/middlegame boundary (ply 20) — or,
    for a game that ended before ply 20, the last recorded ply, so a short
    game still gets judged on the position it actually reached. None if the
    game has no move_evals rows at all."""
    if not rows:
        return None
    row20 = next((r for r in rows if r.ply == 20), None)
    row = row20 if row20 is not None else max(rows, key=lambda r: r.ply)
    return player_pov_eval(row.eval_cp_after, game.player_color)


def _opening_leak(game: Game, rows: list[MoveEval]) -> bool:
    """True if the player was already meaningfully worse by the opening's
    end — FEATURE_OPENING_LEAK_CP read from the player's own side via
    player_pov_eval (Cardinal Rule 7's other sanctioned conversion)."""
    pov = _opening_leak_pov_eval(game, rows)
    return pov is not None and pov <= -settings.FEATURE_OPENING_LEAK_CP


def _opening_leak_stats(
    games: list[Game], evals: dict[str, list[MoveEval]]
) -> tuple[float, list[tuple[str, int]]]:
    """Rate + evidence over a set of games, built from `_opening_leak` /
    `_opening_leak_pov_eval` above. Evidence cites the games with the
    most-negative ply-20 read (the worst leaks), up to 3, each tagged with
    ply 20 — the read point, regardless of whether that particular game
    actually reached ply 20."""
    if not games:
        return 0.0, []

    leak_count = 0
    povs: list[tuple[Game, int]] = []
    for game in games:
        rows = evals.get(str(game.id), [])
        pov = _opening_leak_pov_eval(game, rows)
        if pov is None:
            continue
        povs.append((game, pov))
        if pov <= -settings.FEATURE_OPENING_LEAK_CP:
            leak_count += 1

    rate = round(leak_count / len(games), 2)
    leaking = sorted(
        (gp for gp in povs if gp[1] <= -settings.FEATURE_OPENING_LEAK_CP),
        key=lambda gp: gp[1],
    )
    evidence = [(str(g.id), 20) for g, _pov in leaking[:3]]
    return rate, evidence


def _endgame_entry_row(rows: list[MoveEval]) -> MoveEval | None:
    """The first (lowest-ply) row where this game's phase became 'endgame',
    i.e. the position the player actually entered the endgame in. None if
    the game never reached an endgame phase at all."""
    endgame_rows = [r for r in rows if r.phase == "endgame"]
    if not endgame_rows:
        return None
    return min(endgame_rows, key=lambda r: r.ply)


def _endgame_conversion(
    games: list[Game], evals: dict[str, list[MoveEval]]
) -> tuple[float | None, list[tuple[str, int]]]:
    """Of the games where the player entered the endgame meaningfully ahead
    (player-POV eval at the endgame-entry ply >= FEATURE_ENDGAME_AHEAD_CP),
    what fraction did they actually win? None (never 0.0) when there are zero
    qualifying games — "no data" is not the same claim as "converts nothing",
    and conflating them would be a real coaching lie. Evidence cites up to 3
    qualifying games the player did NOT win, at the endgame-entry ply."""
    qualifying: list[tuple[Game, int]] = []
    for game in games:
        rows = evals.get(str(game.id), [])
        entry = _endgame_entry_row(rows)
        if entry is None:
            continue
        pov = player_pov_eval(entry.eval_cp_before, game.player_color)
        if pov >= settings.FEATURE_ENDGAME_AHEAD_CP:
            qualifying.append((game, entry.ply))

    if not qualifying:
        return None, []

    won = sum(1 for g, _ply in qualifying if g.result == "win")
    conversion = round(won / len(qualifying), 2)
    not_won = [(str(g.id), ply) for g, ply in qualifying if g.result != "win"][:3]
    return conversion, not_won


def _color_stats(
    color_games: list[Game], evals: dict[str, list[MoveEval]]
) -> ColorStats:
    """A full ColorStats for one color's games, reusing every helper above
    exactly as the overall (color-blind) computation does — so a per-color
    number and the overall number can never drift apart from having separate
    math.

    Per-mover stats (class_counts, ACPL, worst_phase) are computed over just
    the PLAYER's own plies in these games (is_player_ply) — every game in
    `color_games` shares the same player_color, so filtering per-game and
    concatenating is equivalent to filtering the concatenated rows. Leak rate
    and endgame conversion stay position-based and read every row via the
    unfiltered `evals` dict, same as the overall computation."""
    player_rows = [
        row
        for g in color_games
        for row in evals.get(str(g.id), [])
        if is_player_ply(row.ply, g.player_color)
    ]
    class_counts = _class_counts(player_rows)
    acpl_overall = _round1(_acpl(player_rows))
    acpl_by_phase = _acpl_by_phase(player_rows)
    worst_phase, _margin = _worst_phase(acpl_by_phase, acpl_overall)
    leak_rate, _leak_evidence = _opening_leak_stats(color_games, evals)
    conversion, _conversion_evidence = _endgame_conversion(color_games, evals)

    return ColorStats(
        games=len(color_games),
        results=_wld(color_games),
        blunders_per_game=round(class_counts.get("blunder", 0) / len(color_games), 1),
        acpl_overall=acpl_overall,
        acpl_by_phase=acpl_by_phase,
        worst_phase=worst_phase,
        opening_leak_rate=leak_rate,
        endgame_conversion=conversion,
        low_signal=len(color_games) < settings.FEATURE_COLOR_MIN_GAMES,
    )


def _meaningful_blunders_per_game(
    games: list[Game],
    player_evals: dict[str, list[MoveEval]],
    detectors: dict,
) -> float:
    """The blunder-inflation resolution (S13): blunders_per_game counts every
    player blunder, including ones played after a lost game's
    point-of-no-return (PONR) — moves in an already-decided game that are
    noise, not signal (see PlayerFeatures.meaningful_blunders_per_game).

    Uses `detect_turning_point`'s `ponr_by_game` (game_id -> ply): a game
    with a PONR only counts player blunders at or before that ply; a game
    with no PONR (never conclusively lost from the player's POV) counts all
    of its player blunders, same as blunders_per_game would."""
    if not games:
        return 0.0

    ponr_by_game: dict[str, int] = detectors.get("turning_point", {}).get("stats", {}).get(
        "ponr_by_game", {}
    )

    total = 0
    for g in games:
        gid = str(g.id)
        ponr = ponr_by_game.get(gid)
        for row in player_evals.get(gid, []):
            if row.classification != "blunder":
                continue
            if ponr is None or row.ply <= ponr:
                total += 1

    return round(total / len(games), 1)


def build_features(
    games: list[Game],
    evals: dict[str, list[MoveEval]],
    rating_snapshot: int | None,
    top_eco_by_color: dict[str, str | None] | None = None,
) -> PlayerFeatures:
    """The pure aggregation entry point: every analyzed game for a player,
    plus that game's move_evals rows (keyed by str(game.id)), in — one fully
    populated PlayerFeatures out. No DB access, no engine — this is what
    tests/test_features.py hand-computes numbers against."""
    games_sorted = sorted(games, key=lambda g: g.played_at or g.created_at)
    games_analyzed = len(games_sorted)

    if games_analyzed == 0:
        return PlayerFeatures(
            games_analyzed=0,
            results=WLD(),
            rating_snapshot=rating_snapshot,
            time_class_mix={},
            blunders_per_game=0.0,
            mistakes_per_game=0.0,
            inaccuracies_per_game=0.0,
            acpl_overall=None,
            acpl_by_phase=PhaseACPL(),
            worst_phase=None,
            worst_phase_margin=None,
            worst_phase_evidence=[],
            accuracy_trend="insufficient_data",
            per_game_acpl=[],
            opening_leak_rate=0.0,
            opening_leak_evidence=[],
            endgame_conversion=None,
            endgame_conversion_evidence=[],
            meaningful_blunders_per_game=0.0,
            by_color={},
            playstyle=compute_playstyle([], {}),
            top_eco_by_color={},
        )

    # move_evals stores a row for EVERY ply of a game — both the player's
    # moves and the opponent's. Every PER-MOVER aggregation below (blunder/
    # mistake/inaccuracy rates, ACPL overall and by phase, per-game ACPL, the
    # color split) must count only the plies the PLAYER actually moved on —
    # a coach reports YOUR blunders, never your opponent's (S13 fix; S12
    # shipped this counting both colors, a real bug). `_opening_leak_*` and
    # `_endgame_conversion` are deliberately NOT filtered: they read a
    # POSITION eval (via player_pov_eval) at a specific ply, not a mover's
    # cp_loss, so they still need every row regardless of whose move it was.
    player_evals: dict[str, list[MoveEval]] = {
        str(g.id): [
            row for row in evals.get(str(g.id), []) if is_player_ply(row.ply, g.player_color)
        ]
        for g in games_sorted
    }
    all_player_rows = [row for g in games_sorted for row in player_evals[str(g.id)]]

    time_class_mix: dict[str, int] = {}
    for g in games_sorted:
        time_class_mix[g.time_class] = time_class_mix.get(g.time_class, 0) + 1

    class_counts = _class_counts(all_player_rows)
    blunders_per_game = round(class_counts.get("blunder", 0) / games_analyzed, 1)
    mistakes_per_game = round(class_counts.get("mistake", 0) / games_analyzed, 1)
    inaccuracies_per_game = round(class_counts.get("inaccuracy", 0) / games_analyzed, 1)

    acpl_overall = _round1(_acpl(all_player_rows))
    acpl_by_phase = _acpl_by_phase(all_player_rows)
    worst_phase, worst_phase_margin = _worst_phase(acpl_by_phase, acpl_overall)
    worst_phase_evidence = _worst_phase_evidence(games_sorted, player_evals, worst_phase)

    per_game_acpl: list[float] = []
    for g in games_sorted:
        value = _acpl(player_evals[str(g.id)])
        if value is not None:
            per_game_acpl.append(round(value, 1))
    accuracy_trend = _accuracy_trend(per_game_acpl)

    opening_leak_rate, opening_leak_evidence = _opening_leak_stats(games_sorted, evals)
    endgame_conversion, endgame_conversion_evidence = _endgame_conversion(games_sorted, evals)

    by_color: dict[str, ColorStats] = {}
    for color in ("white", "black"):
        color_games = [g for g in games_sorted if g.player_color == color]
        if color_games:
            by_color[color] = _color_stats(color_games, evals)

    detectors = run_detectors(games_sorted, evals)
    playstyle = compute_playstyle(games_sorted, evals)
    meaningful_blunders_per_game = _meaningful_blunders_per_game(
        games_sorted, player_evals, detectors
    )

    return PlayerFeatures(
        games_analyzed=games_analyzed,
        results=_wld(games_sorted),
        rating_snapshot=rating_snapshot,
        time_class_mix=time_class_mix,
        blunders_per_game=blunders_per_game,
        mistakes_per_game=mistakes_per_game,
        inaccuracies_per_game=inaccuracies_per_game,
        acpl_overall=acpl_overall,
        acpl_by_phase=acpl_by_phase,
        worst_phase=worst_phase,
        worst_phase_margin=worst_phase_margin,
        worst_phase_evidence=worst_phase_evidence,
        accuracy_trend=accuracy_trend,
        per_game_acpl=per_game_acpl,
        opening_leak_rate=opening_leak_rate,
        opening_leak_evidence=opening_leak_evidence,
        endgame_conversion=endgame_conversion,
        endgame_conversion_evidence=endgame_conversion_evidence,
        meaningful_blunders_per_game=meaningful_blunders_per_game,
        by_color=by_color,
        detectors=detectors,
        playstyle=playstyle,
        top_eco_by_color=top_eco_by_color or {},
    )


# ---------------------------------------------------------------------------
# Thin DB wrapper — the only part of this module that touches a session.
# ---------------------------------------------------------------------------


def load_features(session: Session, platform: str, username: str) -> PlayerFeatures | None:
    """Look up a player by (platform, username), load every analyzed game's
    move_evals rows, and hand them to `build_features`. None if the player
    doesn't exist yet, or exists but has no analyzed games — either way,
    there's nothing to report."""
    player = session.scalars(
        select(Player).where(Player.platform == platform, Player.username == username.lower())
    ).first()
    if player is None:
        return None

    games = session.scalars(
        select(Game).where(Game.player_id == player.id, Game.analyzed_at.is_not(None))
    ).all()
    if not games:
        return None

    evals: dict[str, list[MoveEval]] = {}
    for game in games:
        rows = session.scalars(select(MoveEval).where(MoveEval.game_id == game.id)).all()
        evals[str(game.id)] = list(rows)

    # Compute most-frequent ECO per player_color for the opening recommender (S16).
    top_eco_by_color: dict[str, str | None] = {}
    for color in ("white", "black"):
        color_ecos = [
            g.opening_eco
            for g in games
            if g.player_color == color and g.opening_eco is not None
        ]
        if color_ecos:
            top_eco_by_color[color] = Counter(color_ecos).most_common(1)[0][0]
        else:
            top_eco_by_color[color] = None

    return build_features(list(games), evals, player.rating_snapshot, top_eco_by_color)
