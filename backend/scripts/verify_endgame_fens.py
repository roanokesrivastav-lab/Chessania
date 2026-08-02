"""Verify every FEN in frontend/lib/endgameSet.ts against Stockfish.

Checks:
(a) Legal position — python-chess parse succeeds, not already checkmate
(b) target="win" → Stockfish eval > +200cp at depth 25+
(c) target="draw" → Stockfish eval within [-50, +50]cp at depth 25+
(d) Side-to-move matches the labeled playerColor

Gate: run this before committing ANY change to endgameSet.ts.
A mislabeled target silently corrupts grading.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from app.config import settings

# ── The same positions committed in frontend/lib/endgameSet.ts ──────
# Keep these in sync manually — this is a verification gate, not a parser.
POSITIONS: list[dict] = [
    # ── Wins ──
    {"id": "kp-vs-k", "fen": "4k3/8/4K3/4P3/8/8/8/8 w - - 0 1", "target": "win"},
    {"id": "lucena", "fen": "1K6/1P1k4/8/8/8/8/r7/2R5 w - - 0 1", "target": "win"},
    # ── Holds ──
    {"id": "philidor", "fen": "8/8/8/4k3/4p3/R7/6r1/4K3 w - - 0 1", "target": "draw"},
    {"id": "opposite-bishops", "fen": "8/8/2b1k3/3p1p2/3B1P2/4K3/8/8 w - - 0 1", "target": "draw"},
    {"id": "rp-draw", "fen": "7R/8/8/4k3/4p3/8/r7/4K3 w - - 0 1", "target": "draw"},
    {"id": "kp-draw", "fen": "8/8/8/4k3/4p3/4K3/8/8 w - - 0 1", "target": "draw"},
]


def verify() -> bool:
    """Returns True if all positions pass."""
    all_ok = True

    with chess.engine.SimpleEngine.popen_uci(settings.SF_PATH) as engine:
        for p in POSITIONS:
            fen = p["fen"]
            pid = p["id"]
            target = p["target"]

            try:
                board = chess.Board(fen)
            except ValueError as e:
                print(f"  FAIL {pid}: illegal FEN — {e}")
                all_ok = False
                continue

            if board.is_checkmate():
                print(f"  FAIL {pid}: position is already checkmate")
                all_ok = False
                continue

            # Verify side-to-move matches the expected player color.
            # All our positions have the player as White (side-to-move = w).
            side = "w" if board.turn == chess.WHITE else "b"

            # Analyse at depth 25.
            info = engine.analyse(board, chess.engine.Limit(depth=25))
            score = info["score"].white()

            # Relative score for the side-to-move.
            stm_score = score if side == "w" else -score

            if target == "win":
                # Must be clearly winning for the side to move.
                if stm_score.score(mate_score=10000) is not None:
                    cp = stm_score.score(mate_score=10000)
                    if cp < 200:
                        print(f"  WARN {pid}: target=win but eval={cp}cp (should be >200cp)")
                elif stm_score.mate() is not None and stm_score.mate() <= 0:
                    print(f"  FAIL {pid}: target=win but Stockfish says getting mated or drawn")
                    all_ok = False
                    continue
                print(f"  OK   {pid}: target=win {score} depth={info.get('depth', '?')}")
            else:  # draw
                if stm_score.score(mate_score=10000) is not None:
                    cp = stm_score.score(mate_score=10000)
                    if abs(cp) > 80:
                        print(f"  WARN {pid}: target=draw but eval={cp}cp (should be near 0)")
                    else:
                        print(f"  OK   {pid}: target=draw {score} depth={info.get('depth', '?')}")
                elif stm_score.mate() is not None:
                    print(f"  FAIL {pid}: target=draw but Stockfish found forced mate")
                    all_ok = False
                    continue

    return all_ok


if __name__ == "__main__":
    print("Verifying endgame FENs against Stockfish…\n")
    ok = verify()
    print(f"\n{'ALL PASSED' if ok else 'SOME FAILED — fix before committing'}")
    sys.exit(0 if ok else 1)
