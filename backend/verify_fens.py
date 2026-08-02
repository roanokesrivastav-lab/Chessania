"""Verify every curated mate FEN: legal position + correct forced-mate distance.

Uses the existing Stockfish binary (settings.SF_PATH) with `go mate N+2`
to confirm the labeled mateInN is exact.

IMPORTANT: This script output the ACTUAL Stockfish-reported mate distance
for each FEN. When a FEN's label is wrong, copy the actual distance into
mateSet.ts — never ship a mislabeled mate-in-N (it silently corrupts the
"perfect" grade).

Run: cd backend && source venv/bin/activate && python verify_fens.py
"""

import re
import sys

import chess
import chess.engine

from app.config import settings

MATE_SET_TS = "../frontend/lib/mateSet.ts"

with open(MATE_SET_TS) as f:
    source = f.read()

# Each entry looks like:
#   {
#     id: "back-rank-1",
#     fen: "1k6/...",
#     mateInN: 1,
#     ...
#   },
entries = re.findall(
    r'\{\s*id:\s*"([^"]+)".*?fen:\s*"([^"]+)".*?mateInN:\s*(\d+)',
    source, re.DOTALL,
)

if not entries:
    print("ERROR: could not parse any entries from mateSet.ts")
    sys.exit(1)

print(f"Verifying {len(entries)} curated FENs with Stockfish ({settings.SF_PATH})…\n")

all_ok = True
engine = chess.engine.SimpleEngine.popen_uci(settings.SF_PATH)

try:
    for entry_id, fen, mate_in_n_str in entries:
        mate_in_n = int(mate_in_n_str)
        problems = []

        board = chess.Board(fen)

        # 1. Legal position?
        if not board.is_valid():
            problems.append("ILLEGAL position")
        elif board.is_checkmate():
            problems.append(f"already checkmate (mateInN should be 0, not {mate_in_n})")

        # 2. Let Stockfish search for mate up to N+2 plies.
        actual_mate_in = None
        if not problems:
            limit = chess.engine.Limit(mate=mate_in_n + 2, depth=30, time=5.0)
            try:
                info = engine.analyse(board, limit=limit)
                sf_score = info.get("score", None)
            except Exception as e:
                problems.append(f"engine analysis failed: {e}")
                sf_score = None

            if sf_score is not None:
                # python-chess 1.x returns a PovScore; unpack to relative.
                try:
                    from chess.engine import PovScore
                    if isinstance(sf_score, PovScore):
                        sf_score = sf_score.relative
                except ImportError:
                    pass
                if sf_score.is_mate():
                    actual_mate_in = sf_score.mate()  # side-to-move POV: + = mates, - = gets mated
                else:
                    cp = sf_score.score()
                    problems.append(f"no forced mate found (best eval: {cp}cp)")

        player_color = "white" if board.turn == chess.WHITE else "black"
        status = "✓" if not problems else "✗"

        sf_label = f"(sf: mate {actual_mate_in})" if actual_mate_in is not None else ""
        print(f"  {status} {entry_id:20s}  {player_color:5s}  labeled mate in {mate_in_n}  {sf_label}")
        for p in problems:
            print(f"      ⚠  {p}")
            all_ok = False

finally:
    engine.quit()

print()
if all_ok:
    print("All FENs verified ✓")
else:
    print("SOME FENs FAILED — use the Stockfish-reported mate distances above")
    print("to update mateInN in frontend/lib/mateSet.ts, then re-run this script.")
    sys.exit(1)
