"use client";
// V2-S4: Client-side engine seam — mirrors backend/app/engine_eval.py.
//
// Engine interface: evaluate(fen) → {evalCp, bestMoveUci}
//
// StockfishWasmEngine: real stockfish-18-lite-single in a Web Worker.
//   Single-threaded, ~7MB (the "lite" NNUE net) — no SharedArrayBuffer, no
//   COOP/COEP headers needed. Depth 12 (matching v1's SF_DEPTH).
//
//   The vendor file (public/stockfish/stockfish-18-lite-single.js) is
//   instantiated AS the Worker directly — `new Worker(thatFile)` — never
//   importScripts()'d from a relay script. The build resolves its .wasm by
//   replacing the loading script's own URL .js->.wasm, so it MUST be the
//   worker's own entry point; a relay's importScripts() call leaves
//   self.location pointed at the RELAY's URL, so the engine looks for a
//   same-named .wasm next to the relay instead and 404s. Keep the .js/.wasm
//   pair's basenames identical and in the same directory.
//
// FixtureEngine: canned answers from a Map<fen, {evalCp, bestMoveUci}>.
//   Throws clearly on unmapped FENs. Used for hand-verification of grade().
//
// gradeMove(): pure function. Given eval_before_cp (White POV), the player's
//   color, and eval_after_cp from the engine (White POV), computes cp_loss
//   using analysis.py's exact formula and returns "perfect" | "pass" | "fail".

// ── Constants ────────────────────────────────────────────────────────

/** Mirrors analysis.py's _BLUNDER_CP = 200. cp_loss < 200 → pass. */
const BLUNDER_CP = 200;

/** Mirrors v1's SF_DEPTH = 12. */
const ENGINE_DEPTH = 12;

/** Mate scores are mapped to this magnitude, mirroring the backend's
 *  EVAL_CLAMP = 1000 so a forced mate reads as ±1000cp on the SAME scale as
 *  the stored White-POV evals gradeMove() compares against. */
const MATE_SCORE = 1000;

// ── Types ────────────────────────────────────────────────────────────

export interface EvalResult {
  evalCp: number; // White POV, clamped
  bestMoveUci: string;
  /** Side-to-move POV mate distance: positive = side to move mates in N,
   *  negative = side to move gets mated in N.  null when the latest score
   *  was a centipawn eval (not a forced mate).  V2-S8. */
  mateIn: number | null;
}

export interface EvaluateOptions {
  /** When set, sends `go movetime <n>` instead of the default `go depth N`.
   *  Used for real-time opponent moves (V2-S6). */
  movetimeMs?: number;
}

export interface Engine {
  evaluate(fen: string, opts?: EvaluateOptions): Promise<EvalResult>;
  /** Configure the engine's UCI_LimitStrength + UCI_Elo. Confirms via
   *  isready/readyok before resolving. V2-S6. */
  configureStrength?(elo: number): Promise<void>;
  close(): void;
}

// ── Web Worker engine ────────────────────────────────────────────────

export class StockfishWasmEngine implements Engine {
  private worker: Worker | null = null;
  private ready = false;
  private initialized: Promise<void>;

  constructor() {
    this.worker = new Worker("/stockfish/stockfish-18-lite-single.js");
    this.initialized = this._init();
  }

  private _init(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.worker) return reject(new Error("Worker not created"));

      let uciOk = false;
      let readyOk = false;

      this.worker.onmessage = (e: MessageEvent) => {
        const line = (e.data ?? "") as string;
        if (!line) return;

        if (line === "uciok") {
          uciOk = true;
        } else if (line === "readyok") {
          readyOk = true;
          if (uciOk && readyOk) {
            this.ready = true;
            resolve();
          }
        }
      };

      this.worker.onerror = (err) => {
        console.error("Stockfish worker error:", err);
        reject(err);
      };

      // `uci` triggers the options list + `uciok`; `isready` triggers `readyok`.
      // BOTH are required — waiting on readyok without ever sending isready
      // leaves `initialized` unresolved forever, hanging every evaluate().
      this.worker.postMessage("uci");
      this.worker.postMessage("isready");
    });
  }

  async evaluate(fen: string, opts?: EvaluateOptions): Promise<EvalResult> {
    await this.initialized;
    if (!this.worker || !this.ready) {
      throw new Error("Stockfish engine not ready");
    }

    const useMovetime = opts?.movetimeMs != null;

    // UCI reports `score` from the SIDE-TO-MOVE's point of view, not White's.
    // Every stored eval in this system is White-POV (backend S8 law), and
    // gradeMove() compares against those — so we convert here: if the searched
    // position has Black to move, negate. `fen` field 2 is the side to move.
    const blackToMove = fen.split(" ")[1] === "b";

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error("Engine timeout"));
      }, useMovetime ? opts!.movetimeMs! * 3 + 10000 : 30000);

      // Latest score seen this search, in SIDE-TO-MOVE POV (converted at resolve).
      let lastRawScore = 0;
      // Latest mate distance, side-to-move POV (null when the score is cp). V2-S8.
      let lastMateIn: number | null = null;

      const handler = (e: MessageEvent) => {
        const line = (e.data ?? "") as string;
        if (!line) return;

        // Track the latest eval. A line has EITHER `score cp` OR `score mate`;
        // a forced mate emits only `score mate`, so both must be handled or a
        // mating line would leave a stale/zero eval and mis-grade the move.
        const cpMatch = line.match(/score cp (-?\d+)/);
        if (cpMatch) {
          lastRawScore = parseInt(cpMatch[1], 10);
          lastMateIn = null;
        } else {
          const mateMatch = line.match(/score mate (-?\d+)/);
          if (mateMatch) {
            const m = parseInt(mateMatch[1], 10);
            lastMateIn = m;
            lastRawScore = m >= 0 ? MATE_SCORE : -MATE_SCORE;
          }
        }

        // Parse "bestmove" to get the result.
        const bestMoveMatch = line.match(/^bestmove (\S+)/);
        if (bestMoveMatch) {
          clearTimeout(timeout);
          this.worker!.removeEventListener("message", handler);
          resolve({
            evalCp: blackToMove ? -lastRawScore : lastRawScore, // → White POV
            bestMoveUci: bestMoveMatch[1],
            mateIn: lastMateIn,
          });
        }
      };

      this.worker!.addEventListener("message", handler);
      this.worker!.postMessage(`position fen ${fen}`);
      if (useMovetime) {
        this.worker!.postMessage(`go movetime ${opts!.movetimeMs}`);
      } else {
        this.worker!.postMessage(`go depth ${ENGINE_DEPTH}`);
      }
    });
  }

  /** Configure UCI_LimitStrength + UCI_Elo for a capped-strength opponent.
   *  Must be called after the engine is initialized, once per game.
   *  Confirms via isready/readyok before resolving. V2-S6. */
  async configureStrength(elo: number): Promise<void> {
    await this.initialized;
    if (!this.worker || !this.ready) {
      throw new Error("Stockfish engine not ready");
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error("configureStrength timeout"));
      }, 5000);

      const handler = (e: MessageEvent) => {
        const line = (e.data ?? "") as string;
        if (line === "readyok") {
          clearTimeout(timeout);
          this.worker!.removeEventListener("message", handler);
          resolve();
        }
      };

      this.worker!.addEventListener("message", handler);
      this.worker!.postMessage("setoption name UCI_LimitStrength value true");
      this.worker!.postMessage(`setoption name UCI_Elo value ${elo}`);
      this.worker!.postMessage("isready");
    });
  }

  close(): void {
    if (this.worker) {
      this.worker.postMessage("quit");
      this.worker.terminate();
      this.worker = null;
    }
  }
}

// ── Fixture engine (offline verification) ────────────────────────────

export class FixtureEngine implements Engine {
  private answers: Map<string, EvalResult>;

  constructor(answers: Map<string, EvalResult>) {
    this.answers = answers;
  }

  async evaluate(fen: string, _opts?: EvaluateOptions): Promise<EvalResult> {
    const result = this.answers.get(fen);
    if (!result) {
      throw new Error(
        `FixtureEngine: no canned answer for FEN: ${fen}`
      );
    }
    // If the canned result doesn't include mateIn, default to null.
    return { ...result, mateIn: result.mateIn ?? null };
  }

  async configureStrength(_elo: number): Promise<void> {
    // No-op: fixture engine doesn't support strength configuration.
  }

  close(): void {}
}

// ── Two-tier grading (pure function) ─────────────────────────────────
//
// Algorithm (Hard Rules):
// 1. If submitted UCI == best_line_uci → "perfect" (no engine call).
// 2. Otherwise, evaluate the position AFTER the submitted move, get
//    eval_after_cp (White POV).
// 3. Compute cp_loss using analysis.py's formula:
//    - White mover: eval_before - eval_after
//    - Black mover: eval_after - eval_before
//    - Floored at 0.
// 4. cp_loss < BLUNDER_CP (200) → "pass", else "fail".

export type Grade = "perfect" | "pass" | "fail";

export function gradeMove(params: {
  submittedUci: string;
  bestLineUci: string;
  evalBeforeCp: number; // White POV
  playerColor: "white" | "black";
  evalAfterCp: number; // White POV, from engine evaluating after the move
}): Grade {
  const { submittedUci, bestLineUci, evalBeforeCp, playerColor, evalAfterCp } = params;

  // Perfect: matched the engine's top move.
  if (submittedUci === bestLineUci) {
    return "perfect";
  }

  // Compute cp_loss — exact formula from analysis.py's cp_loss().
  let cpLoss: number;
  if (playerColor === "white") {
    cpLoss = evalBeforeCp - evalAfterCp;
  } else {
    cpLoss = evalAfterCp - evalBeforeCp;
  }
  cpLoss = Math.max(0, cpLoss);

  return cpLoss < BLUNDER_CP ? "pass" : "fail";
}

// ── Helpers ──────────────────────────────────────────────────────────

/**
 * Derive the player's color from a FEN string.
 * FEN format: ... <side-to-move> ...
 * The FEN stored in TrainingPosition is fen_before — the position before
 * the player's own move. The side-to-move in this FEN is the PLAYER's color.
 */
export function playerColorFromFen(fen: string): "white" | "black" {
  const parts = fen.split(" ");
  return parts[1] === "w" ? "white" : "black";
}

/**
 * Convert a UCI move to SAN using chessops (same libraries Board.tsx uses).
 */
export function uciToSan(fen: string, uci: string): string {
  try {
    // Dynamic import to stay client-only.
    const { Chess } = require("chessops/chess");
    const { parseFen, makeFen } = require("chessops/fen");
    const { makeSan } = require("chessops/san");
    const { parseSquare, makeSquare } = require("chessops/util");
    const { makeUci, parseUci } = require("chessops");

    const setup = parseFen(fen).unwrap();
    const pos = Chess.fromSetup(setup).unwrap();
    const move = parseUci(uci);
    if (!move) return uci; // fallback to UCI
    return makeSan(pos, move);
  } catch {
    return uci; // fallback
  }
}
