"""Session 13 — the distinctive-insight layer.

Session 12's `features.py` produces RATES ("you lose 1.4 pawns a game",
"your endgames fall apart") — averages a coach can quote, but not yet a
diagnosis. This module is the diagnosis layer: six named pattern detectors,
each pattern-matching over the SAME already-stored move_evals + games rows
build_features already has in hand, looking for a specific, nameable
weakness ("you hang pieces after you blunder", "you collapse late in
games", "you leak the opening in your Pirc games", "you blunder when
your clock is low", "you dawdle in simple positions").

Precision-first, deliberately. A rate that's slightly off just reads as an
imprecise number; a DETECTOR that fires when it shouldn't reads as the
product making something up — the founder's own words for this failure
mode are "a horoscope" — so every detector below is written to be quiet by
default and only speak when its evidence is real and specific. Every
detector returns up to 3 concrete (game_id, ply) citations so a downstream
coaching sentence can always point at an actual move, never assert a vibe.

Pure functions, no engine, no network, no DB (Cardinal Rule 6/7 - this
session is PURE ANALYSIS over data Session 8/9 already computed and
persisted; SEE below is a plain python-chess board computation, not an
engine call). Every threshold is a named `app.config.settings.DET_*`
constant — never a bare number at a call site (Cardinal Rule 3).

Perspective discipline carries over unchanged from analysis.py/features.py:
every stored eval is White's POV; `player_pov_eval` (analysis.py, S12) is
the only sanctioned "how good is this position FOR the player" conversion,
and `is_player_ply` (analysis.py, S13) is the only sanctioned "did the
player make this move" test. Detectors use both; neither is reimplemented
here.

Contract: every `detect_*` function takes `(games, evals)` — the same
shapes `build_features` already has (`games`: list[Game],
`evals`: dict[str(game.id) -> list[MoveEval]], ALL rows, both colors) — and
returns exactly:

    {"fired": bool, "stats": {...}, "evidence": [(game_id, ply), ...]}

`run_detectors(games, evals)` calls all nine and returns them keyed by name;
that dict becomes `PlayerFeatures.detectors` verbatim.
"""

from __future__ import annotations

import io
import re

import chess
import chess.pgn

from app.analysis import is_player_ply, player_pov_eval
from app.config import settings
from app.models import Game, MoveEval

# Standard piece values in centipawns, used only by the SEE helper below —
# NOT the engine's own evaluation (that's eval_cp/cp_loss, S8/S9's domain).
# King is given an arbitrarily large value so a SEE swap-off never treats
# "capturing" into check as a real material exchange.
_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

_SQUARE_RE = re.compile(r"([a-h][1-8])")


# ---------------------------------------------------------------------------
# Static Exchange Evaluation — python-chess has no built-in SEE.
# ---------------------------------------------------------------------------


def _see(board: chess.Board, move: chess.Move) -> int:
    """Static exchange evaluation of a capture: the net centipawns the side
    making `move` nets from the full exchange on move.to_square, assuming
    both sides always recapture with their LEAST-valuable attacker and
    either side may choose to stop capturing whenever it isn't profitable
    (the "you don't have to recapture" rule that makes this more than a
    naive material count).

    Standard recursive formulation: capturing nets you the value of what
    you took, minus whatever your opponent's best possible reply is worth
    to THEM (their own recapture-or-decline, computed the same way one ply
    deeper) — floored at 0 because a losing recapture is simply never
    played. `_see_swap` is that one-ply recursive step.
    """
    target = board.piece_at(move.to_square)
    captured_value = _PIECE_VALUES[target.piece_type] if target else 0

    board = board.copy(stack=False)
    attacker = board.piece_at(move.from_square)
    board.remove_piece_at(move.from_square)
    board.set_piece_at(move.to_square, attacker)

    reply = max(0, _see_swap(board, move.to_square, not attacker.color))
    return captured_value - reply


def _see_swap(board: chess.Board, square: chess.Square, side: chess.Color) -> int:
    """One ply of the SEE recursion: the value `side` nets by recapturing on
    `square` right now with its least-valuable attacker, then letting the
    exchange continue recursively from there. 0 if `side` has no attacker of
    `square` at all (attackers are recomputed fresh from the board each call,
    so a piece unmasked by a previous capture — an x-ray attacker — is
    picked up naturally)."""
    attackers = board.attackers(side, square)
    if not attackers:
        return 0

    lva_square = min(attackers, key=lambda sq: _PIECE_VALUES[board.piece_at(sq).piece_type])
    occupant = board.piece_at(square)
    occupant_value = _PIECE_VALUES[occupant.piece_type] if occupant else 0
    attacker = board.piece_at(lva_square)

    board = board.copy(stack=False)
    board.remove_piece_at(lva_square)
    board.set_piece_at(square, attacker)

    reply = max(0, _see_swap(board, square, not side))
    return occupant_value - reply


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _game_eco(game: Game) -> str | None:
    """ECO code for a game: prefer the PGN's own [ECO] tag (every committed
    fixture PGN carries one, and so does Chess.com's raw archive PGN text,
    even though Chess.com's JSON has no separate ECO field for ingest.py to
    read), falling back to games.opening_eco (populated for Lichess). None
    if neither source has it."""
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    eco = parsed.headers.get("ECO") if parsed is not None else None
    return eco or game.opening_eco


def _pawn_move_destination_rank(move_san: str) -> int | None:
    """0-based destination rank (0=rank1 .. 7=rank8) of a SAN PAWN move, or
    None if `move_san` isn't a plain pawn move. Pawn-move SAN never starts
    with a piece letter (K/Q/R/B/N) and is never castling, so a plain-file
    first character is sufficient to identify one; the destination square
    is then read out with `chess.parse_square` rather than hand-rolled
    digit math."""
    if not move_san or move_san[0] not in "abcdefgh":
        return None
    match = _SQUARE_RE.search(move_san)
    if not match:
        return None
    return chess.square_rank(chess.parse_square(match.group(1)))


# ---------------------------------------------------------------------------
# 1. hung_pieces — a player blunder that immediately hangs material
# ---------------------------------------------------------------------------


def detect_hung_pieces(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Of the player's own blunders, how many immediately hang real material
    to the opponent's best reply (SEE >= DET_SEE_MINOR_CP, i.e. at least a
    minor piece's worth)? A player who mostly blunders POSITIONALLY (a bad
    plan, not a hung piece) gets a very different coaching sentence than one
    who's dropping pieces outright — this detector is what tells them apart.
    """
    hangs: list[tuple[str, int, int]] = []  # (game_id, ply, see_value)
    player_blunders = 0

    for game in games:
        rows = evals.get(str(game.id), [])
        by_ply = {row.ply: row for row in rows}

        for row in rows:
            if row.classification != "blunder" or not is_player_ply(row.ply, game.player_color):
                continue
            player_blunders += 1

            reply_row = by_ply.get(row.ply + 1)
            if reply_row is None:
                continue  # the blunder was the game's last recorded ply

            try:
                board = chess.Board(reply_row.fen_before)
                reply_move = board.parse_san(reply_row.best_move_san)
            except ValueError:
                continue  # unparseable — never guess, just skip this citation

            if not board.is_capture(reply_move):
                continue

            see_value = _see(board, reply_move)
            if see_value >= settings.DET_SEE_MINOR_CP:
                hangs.append((str(game.id), row.ply, see_value))

    if player_blunders == 0:
        return {
            "fired": False,
            "stats": {"hang_pct": 0.0, "player_blunders": 0, "hung_count": 0},
            "evidence": [],
        }

    hang_pct = round(len(hangs) / player_blunders * 100, 1)
    fired = (len(hangs) / player_blunders) >= settings.DET_HUNG_MIN_SHARE

    top = sorted(hangs, key=lambda h: h[2], reverse=True)[:3]
    return {
        "fired": fired,
        "stats": {
            "hang_pct": hang_pct,
            "player_blunders": player_blunders,
            "hung_count": len(hangs),
        },
        "evidence": [(gid, ply) for gid, ply, _see_value in top],
    }


# ---------------------------------------------------------------------------
# 2. late_collapse — blunder rate spikes late in the game
# ---------------------------------------------------------------------------


def detect_late_collapse(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Do the player's own blunders cluster in the back half of the game
    (ply > DET_LATE_PLY), at a rate meaningfully higher than earlier on?
    Blunder RATE (not raw count) is what matters — a game simply has more
    late plies than early ones, so a raw count would always look "later
    heavy" even for a perfectly consistent player."""
    early_moves = early_blunders = 0
    late_moves = late_blunders = 0
    late_evidence: list[tuple[str, int]] = []

    for game in games:
        for row in evals.get(str(game.id), []):
            if row.classification == "skipped" or not is_player_ply(row.ply, game.player_color):
                continue
            if row.ply > settings.DET_LATE_PLY:
                late_moves += 1
                if row.classification == "blunder":
                    late_blunders += 1
                    late_evidence.append((str(game.id), row.ply))
            else:
                early_moves += 1
                if row.classification == "blunder":
                    early_blunders += 1

    early_rate = early_blunders / early_moves if early_moves else 0.0
    late_rate = late_blunders / late_moves if late_moves else 0.0

    fired = (
        early_rate > 0
        and late_rate >= settings.DET_LATE_RATIO * early_rate
        and late_blunders >= settings.DET_LATE_MIN_BLUNDERS
    )

    return {
        "fired": fired,
        "stats": {
            "late_ratio": round(late_rate / early_rate, 1) if early_rate > 0 else None,
            "early_rate": round(early_rate, 3),
            "late_rate": round(late_rate, 3),
            "late_blunders": late_blunders,
        },
        "evidence": late_evidence[:3],
    }


# ---------------------------------------------------------------------------
# 3. opening_leak — a specific opening family the player is consistently
#    already-worse out of
# ---------------------------------------------------------------------------


def detect_opening_leak(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Position-based, NOT player-filtered (Rule 7's other sanctioned
    conversion, player_pov_eval, reads a POSITION not a mover's cp_loss):
    group games by ECO family (first two characters of the ECO code, e.g.
    "B07" and "B12" are both family "B0"/"B1"), and for any family with
    enough games, check whether the player is on average already
    meaningfully worse (player-POV eval <= -DET_OPENING_LEAK_CP) by ply 15.
    A generic "you leak the opening" is a vague sentence; "your Pirc games
    specifically" is a coaching insight."""
    families: dict[str, list[tuple[Game, float]]] = {}

    for game in games:
        eco = _game_eco(game)
        if not eco or len(eco) < 2:
            continue

        rows = evals.get(str(game.id), [])
        row15 = next((r for r in rows if r.ply == 15), None)
        if row15 is None:
            earlier = [r for r in rows if r.ply <= 15]
            row15 = max(earlier, key=lambda r: r.ply) if earlier else None
        if row15 is None:
            continue

        pov = player_pov_eval(row15.eval_cp_after, game.player_color)
        families.setdefault(eco[:2], []).append((game, pov))

    worst_family: str | None = None
    worst_avg: float | None = None
    for family, entries in families.items():
        if len(entries) < settings.DET_OPENING_FAMILY_MIN_GAMES:
            continue
        avg_cp = sum(pov for _game, pov in entries) / len(entries)
        if avg_cp <= -settings.DET_OPENING_LEAK_CP and (worst_avg is None or avg_cp < worst_avg):
            worst_avg = avg_cp
            worst_family = family

    if worst_family is None:
        return {"fired": False, "stats": {}, "evidence": []}

    entries = families[worst_family]
    # game_count keeps the FULL family size (the coach's "across {k} games"
    # copy), but evidence honors the module's up-to-3 contract — cite the 3
    # WORST offenders (most-negative player-POV eval first), same as
    # hung_pieces cites its 3 clearest hangs, not an arbitrary first three.
    worst_first = sorted(entries, key=lambda gp: gp[1])
    return {
        "fired": True,
        "stats": {
            "family": worst_family,
            "avg_cp": round(worst_avg, 1),
            "game_count": len(entries),
        },
        "evidence": [(str(game.id), 15) for game, _pov in worst_first[:3]],
    }


# ---------------------------------------------------------------------------
# 4. overextension — a pawn pushed deep into enemy territory precedes a
#    big eval swing against the player
# ---------------------------------------------------------------------------


def detect_overextension(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Low-confidence pattern (see `confidence` in stats — this correlation
    is much weaker evidence than the other five detectors, which is why it
    always carries the hedge): the player pushes a pawn to their 6th rank
    or beyond, and within DET_OVEREXT_WINDOW plies the position swings
    against them by DET_OVEREXT_DROP_CP or more. One occurrence is nothing;
    a repeated pattern across games is a real (if soft) signal of
    overextending pawns without support."""
    occurrences: list[tuple[str, int]] = []

    for game in games:
        rows = sorted(evals.get(str(game.id), []), key=lambda r: r.ply)
        by_ply = {row.ply: row for row in rows}

        for row in rows:
            if not is_player_ply(row.ply, game.player_color):
                continue
            rank_idx = _pawn_move_destination_rank(row.move_san)
            if rank_idx is None:
                continue
            if game.player_color == "white" and rank_idx < 5:
                continue
            if game.player_color == "black" and rank_idx > 2:
                continue

            base_pov = player_pov_eval(row.eval_cp_after, game.player_color)
            window = range(row.ply + 1, row.ply + 1 + settings.DET_OVEREXT_WINDOW)
            for later_ply in window:
                later_row = by_ply.get(later_ply)
                if later_row is None:
                    continue
                later_pov = player_pov_eval(later_row.eval_cp_after, game.player_color)
                if base_pov - later_pov >= settings.DET_OVEREXT_DROP_CP:
                    occurrences.append((str(game.id), row.ply))
                    break

    return {
        "fired": len(occurrences) >= settings.DET_OVEREXT_MIN,
        "stats": {"confidence": "low", "occurrences": len(occurrences)},
        "evidence": occurrences[:3],
    }


# ---------------------------------------------------------------------------
# 5. time_class_split — blunders spike in blitz vs rapid
# ---------------------------------------------------------------------------


def detect_time_class_split(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Player blunders-per-game, split by time_class. Requires
    DET_TIMECLASS_MIN_GAMES of EACH class before comparing at all — a
    2-game blitz sample proves nothing. Fires when blitz is at least
    DET_BLITZ_RATIO times worse than rapid."""

    def _per_class(time_class: str) -> tuple[list[Game], float | None, list[tuple[str, int]]]:
        tc_games = [g for g in games if g.time_class == time_class]
        blunders = 0
        evidence: list[tuple[str, int]] = []
        for game in tc_games:
            for row in evals.get(str(game.id), []):
                if is_player_ply(row.ply, game.player_color) and row.classification == "blunder":
                    blunders += 1
                    evidence.append((str(game.id), row.ply))
        bpg = round(blunders / len(tc_games), 2) if tc_games else None
        return tc_games, bpg, evidence

    blitz_games, blitz_bpg, blitz_evidence = _per_class("blitz")
    rapid_games, rapid_bpg, _rapid_evidence = _per_class("rapid")

    fired = (
        len(blitz_games) >= settings.DET_TIMECLASS_MIN_GAMES
        and len(rapid_games) >= settings.DET_TIMECLASS_MIN_GAMES
        and rapid_bpg is not None
        and rapid_bpg > 0
        and blitz_bpg is not None
        and blitz_bpg >= settings.DET_BLITZ_RATIO * rapid_bpg
    )

    return {
        "fired": fired,
        "stats": {
            "blitz_bpg": blitz_bpg,
            "rapid_bpg": rapid_bpg,
            "blitz_games": len(blitz_games),
            "rapid_games": len(rapid_games),
        },
        "evidence": blitz_evidence[:3],
    }


# ---------------------------------------------------------------------------
# 6. turning_point — the ply after which a lost game was permanently lost
# ---------------------------------------------------------------------------


def detect_turning_point(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Per game, find the point-of-no-return (PONR): scanning the
    chronological player-POV eval sequence (player_pov_eval(eval_cp_after,
    color) at every recorded ply, both movers — this is a POSITION read,
    not a mover's cp_loss), walk backward from the game's last recorded ply
    to find the LAST ply that was still "playable" (player-POV eval >
    -DET_PLAYABLE_CP). The PONR is the very next ply after that — the first
    ply of the final, unbroken doomed stretch. If the game's last recorded
    eval is itself still playable, the player was never conclusively lost
    from their own POV, so the game has no PONR at all.

    `ponr_by_game` is exposed in stats for EVERY game with a PONR (not just
    "qualifying" ones below) — `features._meaningful_blunders_per_game`
    reads it to exclude a game's post-PONR blunders as noise from an
    already-decided position.

    A game additionally "qualifies" (adds a citable insight, and is what
    `fired`/evidence are keyed on) only when the PONR ply is NOT the same
    ply as the player's own single worst blunder in that game — i.e. the
    game was lost by a slide over several moves, not by one identifiable
    blunder (which worst_phase_evidence / blunders_per_game already surface
    perfectly well on their own).
    """
    ponr_by_game: dict[str, int] = {}
    qualifying: list[tuple[str, int]] = []

    for game in games:
        rows = sorted(evals.get(str(game.id), []), key=lambda r: r.ply)
        if not rows:
            continue

        povs = [(row.ply, player_pov_eval(row.eval_cp_after, game.player_color)) for row in rows]

        if povs[-1][1] > -settings.DET_PLAYABLE_CP:
            continue  # never conclusively lost from the player's own POV

        last_ok_index = None
        for i in range(len(povs) - 2, -1, -1):
            if povs[i][1] > -settings.DET_PLAYABLE_CP:
                last_ok_index = i
                break

        ponr_ply = povs[0][0] if last_ok_index is None else povs[last_ok_index + 1][0]
        ponr_by_game[str(game.id)] = ponr_ply

        player_rows = [
            r for r in rows if is_player_ply(r.ply, game.player_color) and r.classification != "skipped"
        ]
        if not player_rows:
            continue
        worst = max(player_rows, key=lambda r: r.cp_loss)
        if worst.ply != ponr_ply:
            qualifying.append((str(game.id), ponr_ply))

    return {
        "fired": len(qualifying) >= 1,
        "stats": {"ponr_by_game": ponr_by_game, "qualifying_games": len(qualifying)},
        "evidence": qualifying,
    }


# ---------------------------------------------------------------------------
# 7. rushed_blunders — blunders made with very little time left
# ---------------------------------------------------------------------------


def detect_rushed_blunders(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Of the player's own blunders, how many were made with less than
    DET_TIME_RUSH_SECONDS left on the clock? A high share of low-clock
    blunders means the player is moving before they've finished looking.
    The LOCKED RULE is satisfied intrinsically here: a blunder played with
    < DET_TIME_RUSH_SECONDS remaining is by definition a rushed blunder,
    not a slow one.
    """
    rushed: list[tuple[float, str, int]] = []  # (remaining_clock, game_id, ply)
    clocked_blunders = 0

    for game in games:
        clocks = _remaining_clock_by_ply(game)
        if not any(v is not None for v in clocks.values()):
            continue  # clockless game — can't say anything about time
        for row in evals.get(str(game.id), []):
            if row.classification != "blunder" or not is_player_ply(row.ply, game.player_color):
                continue
            remaining = clocks.get(row.ply)
            if remaining is None:
                continue
            clocked_blunders += 1
            if remaining < settings.DET_TIME_RUSH_SECONDS:
                rushed.append((remaining, str(game.id), row.ply))

    if clocked_blunders == 0:
        return {
            "fired": False,
            "stats": {
                "rushed": 0,
                "clocked_blunders": 0,
                "share": 0.0,
                "rush_seconds": settings.DET_TIME_RUSH_SECONDS,
            },
            "evidence": [],
        }

    rushed_count = len(rushed)
    share = rushed_count / clocked_blunders
    fired = (
        clocked_blunders >= settings.DET_TIME_RUSH_MIN_BLUNDERS
        and share >= settings.DET_TIME_RUSH_MIN_SHARE
    )

    # Cite the rushed blunders with the LOWEST remaining clock — the clearest.
    top = sorted(rushed, key=lambda r: r[0])[:3]
    return {
        "fired": fired,
        "stats": {
            "rushed": rushed_count,
            "clocked_blunders": clocked_blunders,
            "share": round(share, 3),
            "rush_seconds": settings.DET_TIME_RUSH_SECONDS,
        },
        "evidence": [(gid, ply) for _rem, gid, ply in top],
    }


# ---------------------------------------------------------------------------
# 8. time_trouble_collapse — error rate spikes once the clock runs low
# ---------------------------------------------------------------------------


def detect_time_trouble_collapse(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Does the player's error rate spike once their remaining clock drops
    below DET_TIME_TROUBLE_CLOCK? Compares error rate (mistakes + blunders
    per move) in time trouble vs at normal clock, requiring enough games to
    have actually reached time trouble before saying anything.
    """
    low_moves = low_errors = 0
    normal_moves = normal_errors = 0
    low_evidence: list[tuple[float, str, int]] = []  # (remaining_clock, game_id, ply)
    games_in_trouble = 0

    for game in games:
        clocks = _remaining_clock_by_ply(game)
        if not any(v is not None for v in clocks.values()):
            continue  # clockless game — can't say anything about time
        saw_low = False
        for row in evals.get(str(game.id), []):
            if not is_player_ply(row.ply, game.player_color):
                continue
            remaining = clocks.get(row.ply)
            if remaining is None:
                continue
            if remaining < settings.DET_TIME_TROUBLE_CLOCK:
                saw_low = True
                low_moves += 1
                if row.classification in ("mistake", "blunder"):
                    low_errors += 1
                    low_evidence.append((remaining, str(game.id), row.ply))
            else:
                normal_moves += 1
                if row.classification in ("mistake", "blunder"):
                    normal_errors += 1
        if saw_low:
            games_in_trouble += 1

    rate_low = low_errors / low_moves if low_moves else 0.0
    rate_normal = normal_errors / normal_moves if normal_moves else 0.0

    fired = (
        games_in_trouble >= settings.DET_TIME_TROUBLE_MIN_GAMES
        and normal_moves > 0
        and rate_low >= settings.DET_TIME_TROUBLE_RATIO * rate_normal
    )

    # Cite the low-clock errors with the lowest remaining clock.
    top = sorted(low_evidence, key=lambda r: r[0])[:3]
    return {
        "fired": fired,
        "stats": {
            "rate_low": round(rate_low, 3),
            "rate_normal": round(rate_normal, 3),
            "games_in_trouble": games_in_trouble,
            "low_clock": settings.DET_TIME_TROUBLE_CLOCK,
        },
        "evidence": [(gid, ply) for _rem, gid, ply in top],
    }


# ---------------------------------------------------------------------------
# 9. dawdling — slow moves in simple positions that later cost time
# ---------------------------------------------------------------------------


def detect_dawdling(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict:
    """Does the player burn DET_TIME_DAWDLE_SECONDS or more on low-cost
    ("ok") moves in simple positions, then later land in time trouble?
    The complexity gate (<= DET_TIME_DAWDLE_MAX_LEGAL legal moves) honors
    the LOCKED RULE: time spent thinking on genuinely hard positions is
    good judgment, not a flaw, and is never counted here.
    """
    dawdles: list[tuple[int, str, int]] = []  # (seconds_spent, game_id, ply)
    qualifying_games: set[str] = set()

    for game in games:
        clocks = _remaining_clock_by_ply(game)
        if not any(v is not None for v in clocks.values()):
            continue  # clockless game — can't say anything about time

        # Find the FIRST player ply that reached time trouble, if any.
        # A dawdle only counts if it happened *before* that point.
        trouble_ply: int | None = None
        for ply, remaining in clocks.items():
            if (
                remaining is not None
                and remaining < settings.DET_TIME_TROUBLE_CLOCK
                and is_player_ply(ply, game.player_color)
            ):
                trouble_ply = ply
                break
        if trouble_ply is None:
            continue

        game_dawdled = False
        for row in evals.get(str(game.id), []):
            if not is_player_ply(row.ply, game.player_color):
                continue
            if row.ply >= trouble_ply:
                continue
            if row.classification != "ok" or row.seconds_spent is None:
                continue
            if row.seconds_spent < settings.DET_TIME_DAWDLE_SECONDS:
                continue
            try:
                board = chess.Board(row.fen_before)
                if board.legal_moves.count() > settings.DET_TIME_DAWDLE_MAX_LEGAL:
                    continue
            except ValueError:
                continue
            dawdles.append((row.seconds_spent, str(game.id), row.ply))
            game_dawdled = True

        if game_dawdled:
            qualifying_games.add(str(game.id))

    fired = len(qualifying_games) >= settings.DET_TIME_DAWDLE_MIN_GAMES

    avg_seconds = 0.0
    if dawdles:
        avg_seconds = round(sum(s for s, _, _ in dawdles) / len(dawdles), 1)

    # Cite the 3 longest dawdled moves.
    top = sorted(dawdles, key=lambda r: -r[0])[:3]
    return {
        "fired": fired,
        "stats": {
            "confidence": "low",
            "avg_dawdle_seconds": avg_seconds,
            "game_count": len(qualifying_games),
            "dawdle_seconds": settings.DET_TIME_DAWDLE_SECONDS,
        },
        "evidence": [(gid, ply) for _sec, gid, ply in top],
    }


# ---------------------------------------------------------------------------
# Shared helper: remaining clock per ply, parsed from the PGN
# ---------------------------------------------------------------------------


def _remaining_clock_by_ply(game: Game) -> dict[int, float | None]:
    """Return the remaining clock (seconds) after each ply, as recorded in
    the PGN's [%clk] comments. This mirrors `extract_move_times`
    (analysis.py) exactly: same 1-based ply numbering, same walk over the
    mainline, same None when a move has no clock stamp. If every value is
    None the game was clockless; callers use that as a signal to skip it.
    """
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        return {}

    clocks: dict[int, float | None] = {}
    ply = 0
    node = parsed
    while node.variations:
        node = node.variation(0)
        ply += 1
        clocks[ply] = node.clock()

    return clocks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_detectors(games: list[Game], evals: dict[str, list[MoveEval]]) -> dict[str, dict]:
    """Run every detector over the same (games, evals) shapes
    `build_features` already has, keyed by name. This dict becomes
    `PlayerFeatures.detectors` verbatim."""
    return {
        "hung_pieces": detect_hung_pieces(games, evals),
        "late_collapse": detect_late_collapse(games, evals),
        "opening_leak": detect_opening_leak(games, evals),
        "overextension": detect_overextension(games, evals),
        "time_class_split": detect_time_class_split(games, evals),
        "turning_point": detect_turning_point(games, evals),
        "rushed_blunders": detect_rushed_blunders(games, evals),
        "time_trouble_collapse": detect_time_trouble_collapse(games, evals),
        "dawdling": detect_dawdling(games, evals),
    }
