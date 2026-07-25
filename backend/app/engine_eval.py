"""The Evaluator seam — the single most important design move in the pipeline.

EVERY EVAL STORED ANYWHERE IN THIS SYSTEM IS FROM WHITE'S PERSPECTIVE.
Conversion to the mover's own point of view happens in exactly ONE helper
(cp_loss(), added in Session 9) and nowhere else. Two perspectives floating
around loose is the classic chess-engine bug factory — so this file, and
every eval it produces, commits to White's POV without exception.

Why a Protocol (an interface) before there's a second implementation:
`analyze_game` (analysis.py) depends only on the `Evaluator` shape, never on
Stockfish directly. That lets Session 11 slot a `FixtureEvaluator` — which
replays recorded engine answers from disk — into the exact same socket, so
~90% of the project's tests never have to launch a real engine. The interface
is the whole trick.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chess
import chess.engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EvalCache

# Mate scores and any absurd eval are clamped to this magnitude so a forced
# mate reads as a large-but-finite ±1000 centipawns rather than infinity —
# which keeps every downstream average and threshold arithmetic sane.
EVAL_CLAMP = 1000


@dataclass
class EvalResult:
    eval_cp: int  # White's perspective, clamped to ±EVAL_CLAMP (mate = ±EVAL_CLAMP)
    best_move_uci: str


class Evaluator(Protocol):
    def evaluate(self, board: chess.Board) -> EvalResult: ...

    def close(self) -> None: ...


def _clamp(value: int) -> int:
    return max(-EVAL_CLAMP, min(EVAL_CLAMP, value))


class StockfishEvaluator:
    """Drives a real Stockfish binary, with a write-through eval cache.

    The engine is opened ONCE in __init__ and reused for every call (opening
    it per-move would pay the process-startup + UCI-handshake cost each time —
    the S4 lesson). Always close() it, in a finally block, or the process
    leaks.

    If a `cache_session` is provided, every position is looked up in
    `eval_cache` by (fen, depth) before the engine is ever consulted, and
    written back on a miss. Across runs this means common opening positions
    are never re-analyzed; within a single game it means the position shared
    between "after ply N" and "before ply N+1" is computed once.
    """

    def __init__(self, cache_session: Session | None = None):
        self.engine = chess.engine.SimpleEngine.popen_uci(settings.SF_PATH)
        self.cache_session = cache_session
        self.depth = settings.SF_DEPTH
        self.cache_hits = 0
        self.cache_misses = 0

    def evaluate(self, board: chess.Board) -> EvalResult:
        fen = board.fen()

        if self.cache_session is not None:
            cached = self.cache_session.get(EvalCache, (fen, self.depth))
            if cached is not None:
                self.cache_hits += 1
                return EvalResult(eval_cp=cached.eval_cp, best_move_uci=cached.best_move_uci)

        self.cache_misses += 1
        info = self.engine.analyse(board, chess.engine.Limit(depth=self.depth))
        eval_cp = _clamp(info["score"].pov(chess.WHITE).score(mate_score=EVAL_CLAMP))
        best_move_uci = info["pv"][0].uci()

        if self.cache_session is not None:
            self.cache_session.add(
                EvalCache(
                    fen=fen,
                    depth=self.depth,
                    eval_cp=eval_cp,
                    best_move_uci=best_move_uci,
                )
            )
            # Flush (not commit) so a later position in this same run that
            # repeats this fen sees the row on its cache lookup. The caller
            # owns the commit that makes it durable across runs.
            self.cache_session.flush()

        return EvalResult(eval_cp=eval_cp, best_move_uci=best_move_uci)

    def close(self) -> None:
        self.engine.quit()
