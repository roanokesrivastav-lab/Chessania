import type { OpeningLineStat } from "@/lib/types";
import StatExplainer from "./StatExplainer";

interface Props {
  lines: OpeningLineStat[];
}

// Verdict label only — the numbers themselves always come from the contract.
// IMPORTANT: if you tune these in backend/app/config.py (FEATURE_OPENING_FINE_CP /
// COACH_OPENING_VARIATION_LOSS), mirror the new values here or the label drifts.
const FINE_CP = -50;
const LOSS_SHARE = 0.5;

function verdict(line: OpeningLineStat): { label: string; cls: string } {
  const lossShare = line.results.loss / line.games;
  if (line.avg_opening_eval >= FINE_CP && lossShare >= LOSS_SHARE) {
    return {
      label: "Fine out of the opening — losing anyway",
      cls: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-100",
    };
  }
  if (line.avg_opening_eval < FINE_CP) {
    return {
      label: "Comes out worse",
      cls: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100",
    };
  }
  return {
    label: "Comes out fine",
    cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100",
  };
}

function formatEval(cp: number): string {
  const rounded = Math.round(cp);
  return rounded > 0 ? `+${rounded} cp` : `${rounded} cp`;
}

export default function OpeningPerformance({ lines }: Props) {
  if (lines.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">
        Your openings <StatExplainer id="opening_performance" />
      </h2>
      <div className="space-y-2">
        {lines.map((line) => {
          const v = verdict(line);
          return (
            <div
              key={`${line.color}-${line.eco}`}
              className="rounded-lg border border-foreground/10 p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{line.name}</h3>
                  <p className="mt-0.5 text-xs text-foreground/50">
                    {line.eco} · {line.color} · {line.games} game
                    {line.games === 1 ? "" : "s"}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${v.cls}`}
                >
                  {v.label}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-xs text-foreground/50">W-L-D</p>
                  <p className="font-semibold">
                    {line.results.win}–{line.results.loss}–{line.results.draw}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-foreground/50">Avg eval out of book</p>
                  <p className="font-semibold">{formatEval(line.avg_opening_eval)}</p>
                </div>
              </div>
              {line.low_signal && (
                <p className="mt-2 text-xs italic text-foreground/50">
                  Small sample — read lightly.
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
