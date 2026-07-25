"""Session 4 throwaway smoke test: prove the engine works before anything
is built on top of it.

Opens Stockfish ONCE and reuses it for both positions — never reopen the
engine per move. Each open pays a real startup cost (spawning a process
and completing the UCI handshake); analyze.py (Session 8) opens the
engine exactly once per analysis job for the same reason.

Run: python scripts/engine_hello.py
"""

import sys
from pathlib import Path

# Let this script import `app` when run directly (python scripts/engine_hello.py)
# instead of only via `python -m` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess
import chess.engine

from app.config import settings


def show_position(engine: chess.engine.SimpleEngine, board: chess.Board, label: str) -> None:
    info = engine.analyse(board, chess.engine.Limit(depth=settings.SF_DEPTH))
    score = info["score"]
    best_move = info.get("pv", [None])[0]

    # The perspective trap (roadmap's own words): python-chess's score is
    # relative to whichever side you ask for — never assume, always call
    # .pov(color) explicitly. Two views on purpose, to make the difference
    # concrete: the mover's own view (the one that finds the checkmate),
    # and White's view (the convention every stored eval in this project
    # uses from Session 8 onward, so cp_loss() has exactly one perspective
    # to convert from).
    mover = "White" if board.turn == chess.WHITE else "Black"
    mover_pov = score.pov(board.turn)
    white_pov = score.pov(chess.WHITE)

    print(f"\n--- {label} ---")
    print(f"FEN: {board.fen()}")
    print(f"Side to move: {mover}")
    print(f"Score, {mover}'s POV: {mover_pov}")
    print(f"Score, White's POV:  {white_pov}")
    print(f"Best move (UCI): {best_move}")
    if best_move is not None:
        print(f"Best move (SAN): {board.san(best_move)}")


def main() -> None:
    engine = chess.engine.SimpleEngine.popen_uci(settings.SF_PATH)
    try:
        starting = chess.Board()
        show_position(engine, starting, "Starting position")

        foolsmate = chess.Board()
        for uci_move in ("f2f3", "e7e5", "g2g4"):
            foolsmate.push_uci(uci_move)
        show_position(engine, foolsmate, "After 1.f3 e5 2.g4 (Black to move, Qh4# available)")
    finally:
        engine.quit()  # always close — an unclosed engine leaks a process


if __name__ == "__main__":
    main()
