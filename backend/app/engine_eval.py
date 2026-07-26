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

Session 11 adds `CachingEvaluator`: the eval_cache lookup + write-through
logic that both StockfishEvaluator and FixtureEvaluator need was previously
duplicated (well, was about to be, the moment a second evaluator existed).
Pulling it into one base class means the caching semantics — same cache key,
same hit/miss counters, same flush-not-commit contract — can never drift
between the real evaluator and its offline stand-in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chess
import chess.engine
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


class CachingEvaluator:
    """Owns the eval_cache lookup + write-through logic shared by every
    Evaluator implementation, so it lives in exactly ONE place.

    Subclasses provide `_compute(board)` — however they actually get an eval
    (a real engine, a fixture file, anything else later) — and get the cache
    semantics for free: `evaluate()` checks `eval_cache` by (fen, depth)
    first, only calling `_compute` on a miss, and writes the result back on
    a miss so the next lookup at the same (fen, depth) is free. `cache_hits`
    / `cache_misses` let callers (tests, calibrate.py) verify the cache is
    actually doing its job.

    Subclasses must set `self.cache_session` and `self.depth` — calling
    `super().__init__(cache_session)` handles cache_session and zeroes the
    hit/miss counters; `self.depth` is set afterward by each subclass
    because it means something different per subclass (SF_DEPTH for the
    real engine, the depth recorded in the fixture file for the replay).
    """

    def __init__(self, cache_session: Session | None):
        self.cache_session = cache_session
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
        result = self._compute(board)

        if self.cache_session is not None:
            self.cache_session.add(
                EvalCache(
                    fen=fen,
                    depth=self.depth,
                    eval_cp=result.eval_cp,
                    best_move_uci=result.best_move_uci,
                )
            )
            # Flush (not commit) so a later position in this same run that
            # repeats this fen sees the row on its cache lookup. The caller
            # owns the commit that makes it durable across runs.
            self.cache_session.flush()

        return result

    def _compute(self, board: chess.Board) -> EvalResult:
        raise NotImplementedError

    def close(self) -> None:
        pass


class StockfishEvaluator(CachingEvaluator):
    """Drives a real Stockfish binary, with a write-through eval cache.

    The engine is opened ONCE in __init__ and reused for every call (opening
    it per-move would pay the process-startup + UCI-handshake cost each time —
    the S4 lesson). Always close() it, in a finally block, or the process
    leaks.

    If a `cache_session` is provided, every position is looked up in
    `eval_cache` by (fen, depth) before the engine is ever consulted, and
    written back on a miss (that bookkeeping lives in CachingEvaluator).
    Across runs this means common opening positions are never re-analyzed;
    within a single game it means the position shared between "after ply N"
    and "before ply N+1" is computed once.
    """

    def __init__(self, cache_session: Session | None = None):
        super().__init__(cache_session)
        self.engine = chess.engine.SimpleEngine.popen_uci(settings.SF_PATH)
        self.depth = settings.SF_DEPTH

    def _compute(self, board: chess.Board) -> EvalResult:
        info = self.engine.analyse(board, chess.engine.Limit(depth=self.depth))
        eval_cp = _clamp(info["score"].pov(chess.WHITE).score(mate_score=EVAL_CLAMP))
        # A terminal position (checkmate/stalemate) has no legal moves, so the
        # engine returns no principal variation — best_move is empty then. The
        # eval is still meaningful (mate/draw). analyze_game only ever reads the
        # best move of the pre-move position (never terminal), so "" here is safe.
        pv = info.get("pv")
        best_move_uci = pv[0].uci() if pv else ""
        return EvalResult(eval_cp=eval_cp, best_move_uci=best_move_uci)

    def close(self) -> None:
        self.engine.quit()


class FixtureMissError(KeyError):
    """Raised when a FixtureEvaluator is asked to evaluate a position that
    was never recorded. This is a real bug — the test/script is analyzing a
    position the fixture file doesn't know about — so it's raised loudly
    rather than papered over with a made-up default."""


class FixtureEvaluator(CachingEvaluator):
    """Replays recorded Stockfish answers from disk instead of launching a
    real engine — the offline drop-in that makes ~90% of this project's
    tests engine-free.

    A fixture file (tests/fixtures/evals/{game_name}.json) is produced once,
    by scripts/record_fixtures.py, by actually running StockfishEvaluator
    over a fixture PGN. From then on, any test that calls
    `FixtureEvaluator(game_name)` gets byte-for-byte the same evals the real
    engine produced, with no engine process, no wall-clock cost, and no
    flakiness — while still exercising the exact same CachingEvaluator
    cache-lookup / write-through path StockfishEvaluator uses in production.

    A position that isn't in the file is never guessed at — `_compute`
    raises `FixtureMissError` naming the fixture, because a miss means the
    test reached a position the fixture never recorded (fix that by
    re-running scripts/record_fixtures.py, not by inventing a number here).
    """

    def __init__(
        self,
        game_name: str,
        cache_session: Session | None = None,
        evals_dir: Path | None = None,
    ):
        super().__init__(cache_session)
        self.game_name = game_name
        if evals_dir is None:
            evals_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "evals"
        self._path = evals_dir / f"{game_name}.json"

        with self._path.open() as f:
            data = json.load(f)

        meta = data.pop("_meta")
        self.depth = int(meta["depth"])
        self._evals: dict[str, EvalResult] = {
            fen: EvalResult(eval_cp=entry["eval_cp"], best_move_uci=entry["best_move_uci"])
            for fen, entry in data.items()
        }

    def _compute(self, board: chess.Board) -> EvalResult:
        fen = board.fen()
        if fen not in self._evals:
            raise FixtureMissError(
                f"position not recorded in fixture '{self.game_name}' ({self._path}): {fen!r} — "
                "re-run scripts/record_fixtures.py if this fixture's PGN changed."
            )
        return self._evals[fen]
