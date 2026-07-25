"""Session 8 manual check: analyze one real game and print a ply-by-ply eval
table, so the founder can eyeball the big swings against the same game open on
chess.com's analysis board (exact numbers differ by depth — the shape is what
must match). Then re-analyze the same game to prove the eval cache makes the
second pass near-instant (~100% cache hits).

Run against a fresh throwaway SQLite DB so it's repeatable:
    python scripts/analyze_hello.py [path/to/game.pgn]
(defaults to the committed Eleven_14 fixture)
"""

import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess.pgn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analysis import analyze_game
from app.db import enable_sqlite_foreign_keys
from app.engine_eval import StockfishEvaluator
from app.models import Base, Game, Player

DEFAULT_PGN = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "pgn"
    / "eleven14_blitz_loss.pgn"
)


def _load_game_row(session: Session, pgn_text: str) -> Game:
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    headers = parsed.headers
    player = Player(platform="chesscom", username=headers.get("White", "unknown").lower())
    session.add(player)
    session.commit()

    game = Game(
        player_id=player.id,
        platform_game_id=headers.get("Link", "manual-check"),
        game_url=headers.get("Link", ""),
        pgn=pgn_text,
        time_class="blitz",
        player_color="white",
        result="loss",
    )
    session.add(game)
    session.commit()
    return game


def _print_table(rows) -> None:
    print(f"\n{'ply':>3} {'move':>7} {'eval_before':>12} {'eval_after':>11} {'best_move':>10}")
    print("-" * 48)
    for r in rows:
        print(
            f"{r.ply:>3} {r.move_san:>7} {r.eval_cp_before:>12} "
            f"{r.eval_cp_after:>11} {r.best_move_san:>10}"
        )


def main() -> None:
    pgn_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PGN
    pgn_text = pgn_path.read_text()

    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        game = _load_game_row(session, pgn_text)
        url = chess.pgn.read_game(io.StringIO(pgn_text)).headers.get("Link", "(no url)")

        # --- First run: cold cache, real engine work ---
        evaluator = StockfishEvaluator(cache_session=session)
        try:
            t0 = time.perf_counter()
            rows = analyze_game(game, evaluator, session)
            t1 = time.perf_counter()
        finally:
            evaluator.close()

        _print_table(rows)
        print(f"\nEyeball these swings against: {url}")
        print(
            f"\nFirst run: {len(rows)} plies analyzed in {t1 - t0:.1f}s "
            f"({evaluator.cache_hits} cache hits, {evaluator.cache_misses} misses)"
        )

        # --- Second run: everything should hit the now-warm cache ---
        evaluator2 = StockfishEvaluator(cache_session=session)
        try:
            t2 = time.perf_counter()
            analyze_game(game, evaluator2, session)
            t3 = time.perf_counter()
        finally:
            evaluator2.close()

        total = evaluator2.cache_hits + evaluator2.cache_misses
        print(
            f"Second run: {t3 - t2:.2f}s "
            f"({evaluator2.cache_hits}/{total} cache hits, {evaluator2.cache_misses} misses)"
        )


if __name__ == "__main__":
    main()
