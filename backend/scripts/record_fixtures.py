"""Session 11 one-time recorder: run the REAL Stockfish engine over every
committed PGN fixture and save its answers to tests/fixtures/evals/*.json.

Those JSON files are what FixtureEvaluator (app/engine_eval.py) replays, so
this is the only place in the whole test suite that ever needs to actually
talk to the engine for these four games. Re-run this script whenever a PGN
fixture changes, or SF_DEPTH changes, and commit the regenerated JSON.

Uses the committed PGN fixtures (network-free) and a throwaway in-memory DB,
same pattern as scripts/calibrate.py.
Run: python scripts/record_fixtures.py
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess.pgn
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.analysis import analyze_game
from app.config import settings
from app.db import enable_sqlite_foreign_keys
from app.engine_eval import StockfishEvaluator
from app.models import Base, EvalCache, Game, Player

PGN_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pgn"
EVALS_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "evals"


def _load(session: Session, pgn: str) -> Game:
    """Insert a throwaway Player + Game for this PGN. player_color/result
    don't affect which positions get evaluated — analyze_game walks every
    ply's before/after regardless of whose move it is — so both are just
    fixed to a valid value here; only the positions matter for recording."""
    headers = chess.pgn.read_game(io.StringIO(pgn)).headers
    player = Player(platform="chesscom", username=headers.get("White", "u").lower())
    session.add(player)
    session.commit()
    game = Game(
        player_id=player.id,
        platform_game_id=headers.get("Link", "record"),
        game_url=headers.get("Link", ""),
        pgn=pgn,
        time_class="blitz",
        player_color="white",
        result="win",
    )
    session.add(game)
    session.commit()
    return game


def main() -> None:
    EVALS_DIR.mkdir(parents=True, exist_ok=True)

    for pgn_path in sorted(PGN_DIR.glob("*.pgn")):
        stem = pgn_path.stem
        pgn = pgn_path.read_text()

        db_engine = create_engine("sqlite:///:memory:")
        enable_sqlite_foreign_keys(db_engine)
        Base.metadata.create_all(db_engine)

        with Session(db_engine) as session:
            game = _load(session, pgn)
            evaluator = StockfishEvaluator(cache_session=session)
            try:
                engine_name = evaluator.engine.id.get("name", "Stockfish")
                analyze_game(game, evaluator, session)
            finally:
                evaluator.close()

            cached = session.scalars(select(EvalCache)).all()
            out: dict = {"_meta": {"engine": engine_name, "depth": settings.SF_DEPTH}}
            for row in cached:
                out[row.fen] = {"eval_cp": row.eval_cp, "best_move_uci": row.best_move_uci}

            out_path = EVALS_DIR / f"{stem}.json"
            out_path.write_text(json.dumps(out, indent=2, sort_keys=False))

            print(f"{stem}: recorded {len(cached)} positions")


if __name__ == "__main__":
    main()
