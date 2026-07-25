"""Per-game analysis: one game in, a full set of per-move evals out.

Session 8 scope: RAW NUMBERS ONLY. This module records, for every half-move
(ply) of a game, the eval before and after the move (both White's POV, from
the Evaluator) and the engine's preferred move. It does NOT yet compute
cp_loss, classify moves, or tag phases — those are Session 9's job, and the
three columns they own (`cp_loss`, `classification`, `phase`) are NOT NULL in
the schema, so this session writes safe provisional placeholders that Session
9 overwrites. Nothing reads `move_evals` before Session 12, so the
placeholders are never observed.
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

# Session 9 replaces all three of these with real computed values.
_PLACEHOLDER_CP_LOSS = 0
_PLACEHOLDER_CLASSIFICATION = "ok"
_PLACEHOLDER_PHASE = "middlegame"


def analyze_game(game: Game, evaluator: Evaluator, session: Session) -> list[MoveEval]:
    """Replay a game's mainline and persist one move_evals row per ply.

    Idempotent: any existing move_evals for this game are deleted first, so
    re-analyzing the same game (Session 9 does exactly this, cheaply, off the
    warm eval cache) never collides with the unique(game_id, ply) constraint.
    A single commit at the end persists both the move_evals rows and the
    eval_cache write-throughs the evaluator produced along the way.
    """
    parsed = chess.pgn.read_game(io.StringIO(game.pgn))
    if parsed is None:
        raise ValueError(f"could not parse PGN for game {game.id}")

    # Clear any prior analysis for this game (idempotent re-runs).
    session.execute(delete(MoveEval).where(MoveEval.game_id == game.id))

    board = parsed.board()
    rows: list[MoveEval] = []
    ply = 0

    for move in parsed.mainline_moves():
        ply += 1

        fen_before = board.fen()
        before = evaluator.evaluate(board)
        move_san = board.san(move)
        # The engine's preferred move is named from the position BEFORE the
        # actual move was played (that's the position it was asked about).
        best_move_san = board.san(chess.Move.from_uci(before.best_move_uci))

        board.push(move)
        after = evaluator.evaluate(board)

        rows.append(
            MoveEval(
                game_id=game.id,
                ply=ply,
                move_san=move_san,
                fen_before=fen_before,
                eval_cp_before=before.eval_cp,
                eval_cp_after=after.eval_cp,
                cp_loss=_PLACEHOLDER_CP_LOSS,  # Session 9
                best_move_san=best_move_san,
                classification=_PLACEHOLDER_CLASSIFICATION,  # Session 9
                phase=_PLACEHOLDER_PHASE,  # Session 9
            )
        )

    session.add_all(rows)
    game.analyzed_at = dt.datetime.now(dt.timezone.utc)
    session.commit()

    return rows
