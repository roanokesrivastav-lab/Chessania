"""Session 9 calibration: analyze the 3 Phase-0 ground-truth games and print the
FOUNDER's own flagged moves (inaccuracy / mistake / blunder, excluding skipped),
so the pipeline's blunder story can be eyeballed against the P0-3 annotations in
STATE.md. Roadmap S9 §6: blunder-level disagreements are bugs — investigate.

Uses the committed PGN fixtures (network-free) and a throwaway in-memory DB.
Run: python scripts/calibrate.py
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
import chess.pgn
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.analysis import analyze_game
from app.db import enable_sqlite_foreign_keys
from app.detectors import run_detectors
from app.engine_eval import FixtureEvaluator, StockfishEvaluator
from app.models import Base, Game, MoveEval, Player

PGN_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pgn"

GROUND_TRUTH = [
    ("gt_cleanwin.pgn", "white", "CLEAN WIN — expect ~0 founder blunders (precision)"),
    ("gt_piecedrop.pgn", "black", "POSITIONAL DECLINE — expect 16.dxc4 mistake -> 19.Rd7 blunder; 22.Nh3 ok"),
    ("gt_lostendgame.pgn", "black", "LOST ENDGAME — expect the decisive error tagged endgame"),
]


def _load(session: Session, pgn: str, color: str) -> Game:
    headers = chess.pgn.read_game(io.StringIO(pgn)).headers
    username = headers.get(color.capitalize(), "u").lower()
    # Reuse an existing player row rather than inserting a fresh one every
    # call: main() gives each fixture its own throwaway in-memory engine (no
    # collision possible), but calibrate_detectors() below shares ONE
    # session across all 3 GT fixtures, two of which are the same founder
    # account ("Eleven_14") — a second unconditional insert would trip the
    # (platform, username) unique constraint.
    p = session.query(Player).filter_by(platform="chesscom", username=username).first()
    if p is None:
        p = Player(platform="chesscom", username=username)
        session.add(p)
        session.commit()
    g = Game(
        player_id=p.id,
        platform_game_id=headers.get("Link", "cal"),
        game_url=headers.get("Link", ""),
        pgn=pgn,
        time_class="blitz",
        player_color=color,
        result="win" if color == "white" else "loss",
    )
    session.add(g)
    session.commit()
    return g


def main() -> None:
    for fname, color, expectation in GROUND_TRUTH:
        pgn = (PGN_DIR / fname).read_text()
        engine = create_engine("sqlite:///:memory:")
        enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            game = _load(session, pgn, color)
            evaluator = StockfishEvaluator(cache_session=session)
            try:
                analyze_game(game, evaluator, session)
            finally:
                evaluator.close()

            rows = session.scalars(
                select(MoveEval).where(MoveEval.game_id == game.id).order_by(MoveEval.ply)
            ).all()

            # Founder's moves: White = odd plies, Black = even plies.
            founder_is_white = color == "white"
            flagged = [
                r
                for r in rows
                if ((r.ply % 2 == 1) == founder_is_white)
                and r.classification in ("inaccuracy", "mistake", "blunder")
            ]

            print(f"\n===== {fname}  ({color}) =====")
            print(f"  expectation: {expectation}")
            print(f"  {'mv':>4} {'move':>7} {'cp_loss':>7} {'phase':>10} {'class':>10} {'secs':>5}")
            for r in flagged:
                movenum = (r.ply + 1) // 2
                secs = "" if r.seconds_spent is None else str(r.seconds_spent)
                print(
                    f"  {movenum:>4} {r.move_san:>7} {r.cp_loss:>7} "
                    f"{r.phase:>10} {r.classification:>10} {secs:>5}"
                )
            blunders = [r for r in flagged if r.classification == "blunder"]
            print(f"  -> {len(flagged)} flagged ({len(blunders)} blunders)")


def calibrate_detectors() -> None:
    """Session 13 sibling to main(): run the six S13 detectors over the same
    3 ground-truth fixture games, so the founder can spot-check whether a
    detector firing (or staying quiet) matches what they remember about
    these games. Uses FixtureEvaluator (recorded evals, replayed from disk)
    rather than main()'s real StockfishEvaluator — no engine, no network,
    same discipline as the test suite (Rule 6)."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        games: list[Game] = []
        evals: dict[str, list[MoveEval]] = {}
        for fname, color, _expectation in GROUND_TRUTH:
            stem = fname.removesuffix(".pgn")
            pgn = (PGN_DIR / fname).read_text()
            game = _load(session, pgn, color)
            rows = analyze_game(game, FixtureEvaluator(stem, cache_session=session), session)
            games.append(game)
            evals[str(game.id)] = rows

        results = run_detectors(games, evals)

        print("\n===== Session 13 detector calibration (3 GT fixtures) =====")
        for key, result in results.items():
            marker = "FIRED" if result["fired"] else "quiet"
            print(f"\n  [{marker}] {key}")
            if result["fired"]:
                print(f"    stats:    {result['stats']}")
                print(f"    evidence: {result['evidence']}")


if __name__ == "__main__":
    main()
    calibrate_detectors()
