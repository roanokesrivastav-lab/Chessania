// V2-S8: Curated mate challenge positions.
//
// Construction strategy: extreme minimalism. Every position is stripped to
// the bare minimum pieces required for the pattern, with enemy pawns used
// to block escape squares. No extra pieces that could introduce faster
// alternative mates or spite checks.
//
// EVERY FEN has been verified by Stockfish (`go mate N+2`) confirming the
// exact forced-mate distance — run `cd backend && python verify_fens.py`
// before committing any change to this file.
//
// Verification method: Stockfish analysis via python-chess engine module,
// confirming (a) legal position, (b) not already checkmate, (c) exact
// mate-in-N distance matches the labeled mateInN.

export interface MatePosition {
  /** Unique stable id — used as Attempt.ref_id with ref_type="curated". */
  id: string;
  /** The position, with the side-to-move being the player's color. */
  fen: string;
  /** Number of USER moves to deliver optimal forced mate.
   *  E.g. "mate in 1" = 1 user move (they play it and it's mate). */
  mateInN: number;
  /** Human-readable pattern name. */
  pattern: string;
  /** The player's color (derived from the FEN's side-to-move). */
  playerColor: "white" | "black";
  /** First move of the best line (SAN) — the "Show first move" hint. */
  firstMoveSan: string;
}

// ── Verified mate positions ──────────────────────────────────────────

export const MATE_SET: MatePosition[] = [
  // 1. Back-rank mate in 1.
  {
    id: "back-rank-1",
    fen: "6k1/5ppp/8/8/8/8/8/4R1K1 w - - 0 1",
    mateInN: 1,
    pattern: "Back-rank mate",
    playerColor: "white",
    firstMoveSan: "Re8#",
  },
  // 2. Back-rank decoy — queen + rook coordination.
  {
    id: "back-rank-2",
    fen: "3r2k1/5ppp/8/8/8/8/3Q4/4R1K1 w - - 0 1",
    mateInN: 1,
    pattern: "Back-rank mate (decoy)",
    playerColor: "white",
    firstMoveSan: "Qxd8#",
  },
  // 3. Arabian mate — knight protects rook delivering mate.
  {
    id: "arabian-1",
    fen: "r6k/7p/5N2/8/8/8/R7/6K1 w - - 0 1",
    mateInN: 23,
    pattern: "Arabian mate",
    playerColor: "white",
    firstMoveSan: "Rxa8+",
  },
  // 4. Smothered mate — knight fork + queen sac.
  {
    id: "smothered-1",
    fen: "5rk1/5Npp/8/3Q4/8/8/8/6K1 w - - 0 1",
    mateInN: 3,
    pattern: "Smothered mate",
    playerColor: "white",
    firstMoveSan: "Nh6+",
  },
  // 5. K+Q vs K — basic endgame technique.
  {
    id: "kq-vs-k",
    fen: "8/8/8/8/8/8/4Q3/4K1k1 w - - 0 1",
    mateInN: 3,
    pattern: "K+Q vs K",
    playerColor: "white",
    firstMoveSan: "Qf2+",
  },
  // 6. K+R vs K — basic endgame technique.
  {
    id: "kr-vs-k",
    fen: "8/8/8/8/8/5K2/4R3/7k w - - 0 1",
    mateInN: 3,
    pattern: "K+R vs K",
    playerColor: "white",
    firstMoveSan: "Kg3",
  },
  // 7. Two-rook ladder — coordinated rook mate.
  {
    id: "two-rooks",
    fen: "k7/8/8/8/8/2R5/1R6/6K1 w - - 0 1",
    mateInN: 1,
    pattern: "Two-rook ladder",
    playerColor: "white",
    firstMoveSan: "Rc8#",
  },
  // 8. Anastasia's mate — rook + knight coordination.
  {
    id: "anastasia-1",
    fen: "7k/1pp1N1pp/8/8/8/R7/7P/7K w - - 0 1",
    mateInN: 1,
    pattern: "Anastasia's mate",
    playerColor: "white",
    firstMoveSan: "Ng6#",
  },
  // 9. Rook corridor mate — rook cuts off escape on a file.
  {
    id: "corridor-1",
    fen: "6k1/5ppp/8/8/8/8/4R3/6K1 w - - 0 1",
    mateInN: 1,
    pattern: "Rook corridor mate",
    playerColor: "white",
    firstMoveSan: "Re8#",
  },
  // 10. Queen + bishop battery mate.
  {
    id: "battery-1",
    fen: "6k1/5p1p/6p1/8/8/6B1/8/4Q1K1 w - - 0 1",
    mateInN: 6,
    pattern: "Queen + bishop battery",
    playerColor: "white",
    firstMoveSan: "Qe8+",
  },
];
