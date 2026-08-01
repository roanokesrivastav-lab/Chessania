"use client";

import { useState } from "react";
import Board, { type BoardMove } from "@/components/board/Board";

// The Philidor position — the classic drawn rook endgame (Black defends with
// the rook on the 6th rank). A familiar position for trying the board.
const PHILIDOR_FEN = "4k3/8/r7/4P3/8/8/8/4K3 w - - 0 1";

export default function BoardDemoPage() {
  const [fen, setFen] = useState(PHILIDOR_FEN);
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [moves, setMoves] = useState<BoardMove[]>([]);

  const handleMove = (move: BoardMove) => {
    setMoves((prev) => [...prev, move]);
    setFen(move.fen);
  };

  const flip = () => setOrientation((o) => (o === "white" ? "black" : "white"));

  const reset = () => {
    setFen(PHILIDOR_FEN);
    setMoves([]);
  };

  return (
    <main className="min-h-screen bg-bg px-4 py-8 text-text">
      <div className="mx-auto w-full max-w-lg">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gold [font-family:var(--font-mono)]">
          v2 · foundations
        </p>
        <h1 className="mt-2 text-3xl font-semibold [font-family:var(--font-serif)]">
          Board component
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-text-mid">
          The one chessboard wrapper every trainer will reuse — chessground for
          rendering + chessops for legal moves. Play both sides of a Philidor
          position below; illegal moves are simply impossible.
        </p>

        <section className="mt-6 rounded-[14px] border border-border bg-surface p-4 shadow-lg">
          <div className="mb-4 flex items-center justify-between gap-3">
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-dim [font-family:var(--font-mono)]">
              {orientation} to move
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={flip}
                className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-text transition-colors hover:border-gold hover:text-gold [font-family:var(--font-mono)]"
              >
                Flip
              </button>
              <button
                type="button"
                onClick={reset}
                className="rounded-lg bg-gold px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-bg-2 transition-colors hover:bg-gold-2 [font-family:var(--font-mono)]"
              >
                Reset
              </button>
            </div>
          </div>

          <Board
            fen={fen}
            orientation={orientation}
            onMove={handleMove}
            ariaLabel="Philidor position — play either side"
          />

          <div className="mt-4 border-t border-border pt-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-dim [font-family:var(--font-mono)]">
              Move log
            </p>
            {moves.length === 0 ? (
              <p className="mt-2 text-sm text-text-mid">
                No moves yet — drag a piece. The side to move is highlighted.
              </p>
            ) : (
              <ol className="mt-2 max-h-40 space-y-1 overflow-y-auto text-sm [font-family:var(--font-mono)]">
                {moves.map((m, i) => (
                  <li key={i} className="flex items-baseline gap-2 text-text-mid">
                    <span className="w-8 shrink-0 text-right text-text-dim">
                      {i + 1}.
                    </span>
                    <span className="text-text">{m.san}</span>
                    <span className="text-text-dim">
                      {m.from}→{m.to}
                      {m.promotion ? `=${m.promotion}` : ""}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        <p className="mt-4 text-xs leading-relaxed text-text-dim">
          Legal destinations come from chessops — you cannot make an illegal
          move. Promote a pawn to see the Q/R/B/N picker. Flip to view from
          the other side. This demo page will be replaced by the real trainers
          (V2-S4+).
        </p>
      </div>
    </main>
  );
}
