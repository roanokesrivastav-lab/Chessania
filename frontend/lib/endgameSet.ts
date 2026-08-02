// V2-S9: Curated endgame challenge positions.
//
// Construction strategy: verified theoretical endgames. Every position is
// stripped to minimal material for the technique being tested. The player
// (side-to-move) must win or hold against full-strength stockfish.wasm.
//
// EVERY FEN has been verified by Stockfish (depth 25+) confirming the
// correct target outcome — run `cd backend && python verify_endgame_fens.py`
// before committing any change to this file.
//
// Verification method: Stockfish analysis via python-chess engine module,
// confirming (a) legal position, (b) not already terminal, (c) eval
// direction matches the labeled target (win = clearly positive, draw = near 0).

export interface EndgamePosition {
  /** Unique stable id — used as Attempt.ref_id with ref_type="curated". */
  id: string;
  /** The position, with the side-to-move being the player's color. */
  fen: string;
  /** "win" = player must convert a winning position.
   *  "draw" = player must hold a drawn position against the engine. */
  target: "win" | "draw";
  /** The player's color (derived from the FEN's side-to-move). */
  playerColor: "white" | "black";
  /** Human-readable pattern name (e.g. "K+P vs K"). */
  pattern: string;
  /** One-line explanation: why this matters at your level. */
  why: string;
}

// ── Verified endgame positions ───────────────────────────────────────

export const ENDGAME_SET: EndgamePosition[] = [
  // ── Wins ──────────────────────────────────────────────────────────
  {
    id: "kp-vs-k",
    fen: "4k3/8/4K3/4P3/8/8/8/8 w - - 0 1",
    target: "win",
    playerColor: "white",
    pattern: "K+P vs K",
    why: "K+P vs K — master the opposition to promote without stalemating. The most common endgame you'll face.",
  },
  {
    id: "lucena",
    fen: "1K6/1P1k4/8/8/8/8/r7/2R5 w - - 0 1",
    target: "win",
    playerColor: "white",
    pattern: "Lucena position",
    why: "Lucena position — build a bridge with your rook to escort the pawn home. The single most important rook endgame technique.",
  },

  // ── Holds ─────────────────────────────────────────────────────────
  {
    id: "philidor",
    fen: "8/8/8/4k3/4p3/R7/6r1/4K3 w - - 0 1",
    target: "draw",
    playerColor: "white",
    pattern: "Philidor defense",
    why: "Philidor defense — rook on the 3rd rank blocks the enemy king. Drop back to the 8th and check from behind. Save half-points for life.",
  },
  {
    id: "opposite-bishops",
    fen: "8/8/2b1k3/3p1p2/3B1P2/4K3/8/8 w - - 0 1",
    target: "draw",
    playerColor: "white",
    pattern: "Opposite bishops fortress",
    why: "Opposite-colored bishop fortress — your dark-squared bishop blockades their pawns. Their light-squared bishop can't break through.",
  },
  {
    id: "rp-draw",
    fen: "7R/8/8/4k3/4p3/8/r7/4K3 w - - 0 1",
    target: "draw",
    playerColor: "white",
    pattern: "R+P vs R draw",
    why: "R+P vs R defensive draw — keep your king in front of the pawn and check from distance. The enemy king has no shelter.",
  },
  {
    id: "kp-draw",
    fen: "8/8/8/4k3/4p3/4K3/8/8 w - - 0 1",
    target: "draw",
    playerColor: "white",
    pattern: "K+P vs K draw",
    why: "K+P vs K drawn defense — maintain the opposition by staying on the pawn's file. Know when a pawn endgame is drawn before you trade down.",
  },
];
