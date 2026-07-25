"""Per-game analysis: one game in, a full set of classified per-move evals out.

Session 8 recorded raw evals (White's POV) per ply. Session 9 turns those into
coaching-grade labels — the layer every downstream feature, detector, and rule
reads — via four small PURE functions plus the per-move time capture:

- cp_loss()          the ONE place a White-POV eval is converted to the mover's
                     point of view. Every other module reads the stored cp_loss
                     column; this function is where perspective lives, and
                     nowhere else (two perspectives loose = the classic bug).
- classify()         cp_loss + the decided-position rule -> ok/inaccuracy/
                     mistake/blunder/skipped.
- tag_phase()        opening / middlegame / endgame.
- extract_move_times()  per-ply seconds spent, parsed from the PGN's [%clk]
                     comments. CAPTURE ONLY in v1 (roadmap Part G #11 reserves the
                     time-management coaching that will one day read it).

These are pure functions (no engine, no DB) so they're unit-tested offline in
tests/test_analysis.py; only the analyze_game integration needs a real engine.
"""

from __future__ import annotations

import datetime as dt
import io

import chess
import chess.pgn
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.engine_eval import Evaluator
from app.models import Game, MoveEval

# Classification thresholds on cp_loss (mover's POV, floored at 0), per the
# roadmap's locked bands: 0-49 ok · 50-99 inaccuracy · 100-199 mistake · >=200 blunder.
_INACCURACY_CP = 50
_MISTAKE_CP = 100
_BLUNDER_CP = 200
# Above this magnitude the position is already decided; a "blunder" in a
# crushing-or-crushed position is noise, so it's tagged 'skipped' and kept out
# of every downstream rate.
_DECIDED_CP = 800


def cp_loss(eval_before_white_pov: int, eval_after_white_pov: int, mover: chess.Color) -> int:
    """Centipawns the mover lost on this move, from THAT player's point of view,
    floored at 0 (an improving move loses nothing).

    Every stored eval is White's POV (engine_eval.py law). This is the single
    helper that converts to the mover's POV: for White, a drop means before>after;
    for Black, White's eval going UP is Black losing ground, so after-before.
    """
    if mover == chess.WHITE:
        loss = eval_before_white_pov - eval_after_white_pov
    else:
        loss = eval_after_white_pov - eval_before_white_pov
    return max(0, loss)


def classify(cp_loss_value: int, eval_before_white_pov: int) -> str:
    """Label a move from its cp_loss, with the decided-position guard first.

    abs() makes the decided check point-of-view-independent: a White-POV eval of
    +900 (mover crushing) and -900 (mover crushed) both have magnitude 900, which
    is exactly the mover-POV magnitude the rule names.
    """
    if abs(eval_before_white_pov) > _DECIDED_CP:
        return "skipped"
    if cp_loss_value < _INACCURACY_CP:
        return "ok"
    if cp_loss_value < _MISTAKE_CP:
        return "inaccuracy"
    if cp_loss_value < _BLUNDER_CP:
        return "mistake"
    return "blunder"


def tag_phase(fen_before: str, ply: int) -> str:
    """opening = ply <= 20 · endgame = <= 6 non-king, non-pawn pieces left ·
    middlegame = everything else. Opening takes precedence (matches the roadmap's
    listing order) so an early mass-trade still reads as opening by ply."""
    if ply <= 20:
        return "opening"
    board = chess.Board(fen_before)
    heavy_or_minor = sum(
        1
        for piece in board.piece_map().values()
        if piece.piece_type not in (chess.KING, chess.PAWN)
    )
    if heavy_or_minor <= 6:
        return "endgame"
    return "middlegame"


def _parse_time_control(tc: str) -> tuple[int | None, int | None]:
    """'180' -> (180, 0); '180+2' -> (180, 2); anything unparseable / clockless
    (e.g. '-', '1/86400' daily) -> (None, None)."""
    if not tc or tc == "-" or "/" in tc:
        return None, None
    base_s, _, inc_s = tc.partition("+")
    try:
        return int(base_s), int(inc_s) if inc_s else 0
    except ValueError:
        return None, None


def extract_move_times(pgn: str) -> dict[int, int | None]:
    """Per-ply seconds the mover spent, derived from the PGN's [%clk] remaining-
    clock stamps: spent = (that player's previous remaining clock) - (current
    remaining clock) + increment; the first move measures from the base time.
    Returns {ply -> seconds | None}; None whenever a move carries no clock (or the
    TimeControl is unparseable). Capture only — no v1 feature reads this."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return {}

    base, inc = _parse_time_control(game.headers.get("TimeControl", ""))
    prev: dict[chess.Color, int | None] = {chess.WHITE: base, chess.BLACK: base}
    times: dict[int, int | None] = {}

    ply = 0
    node = game
    while node.variations:
        node = node.variation(0)
        ply += 1
        mover = chess.WHITE if ply % 2 == 1 else chess.BLACK
        clk = node.clock()  # seconds remaining after this move, or None
        if clk is None or prev[mover] is None:
            times[ply] = None
        else:
            spent = prev[mover] - clk + (inc or 0)
            times[ply] = max(0, round(spent))
            prev[mover] = clk
    return times


def analyze_game(game: Game, evaluator: Evaluator, session: Session) -> list[MoveEval]:
    """Replay a game's mainline and persist one classified move_evals row per ply.

    Idempotent: existing move_evals for this game are deleted first, so re-analysis
    (this is where Session 9 re-runs over Session 8's rows, cheaply off the warm
    eval cache) never collides with unique(game_id, ply). One commit at the end
    persists both the rows and the evaluator's eval_cache write-throughs.
    """
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        raise ValueError(f"could not parse PGN for game {game.id}")

    session.execute(delete(MoveEval).where(MoveEval.game_id == game.id))

    move_times = extract_move_times(game.pgn)

    board = parsed.board()
    rows: list[MoveEval] = []
    ply = 0

    for move in parsed.mainline_moves():
        ply += 1
        mover = board.turn  # whose move this is (before the push)

        fen_before = board.fen()
        before = evaluator.evaluate(board)
        move_san = board.san(move)
        # The engine's preferred move is named from the position BEFORE the actual
        # move was played (never terminal, so best_move_uci is always populated here).
        best_move_san = board.san(chess.Move.from_uci(before.best_move_uci))

        board.push(move)
        after = evaluator.evaluate(board)

        loss = cp_loss(before.eval_cp, after.eval_cp, mover)

        rows.append(
            MoveEval(
                game_id=game.id,
                ply=ply,
                move_san=move_san,
                fen_before=fen_before,
                eval_cp_before=before.eval_cp,
                eval_cp_after=after.eval_cp,
                cp_loss=loss,
                best_move_san=best_move_san,
                classification=classify(loss, before.eval_cp),
                phase=tag_phase(fen_before, ply),
                seconds_spent=move_times.get(ply),
            )
        )

    session.add_all(rows)
    game.analyzed_at = dt.datetime.now(dt.timezone.utc)
    session.commit()

    return rows
