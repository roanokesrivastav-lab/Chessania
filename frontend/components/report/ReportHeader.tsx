import type { PlayerSummary, Playstyle } from "@/lib/types";
import { formatRating, formatDateRange, platformLabel, playstyleColor } from "@/lib/format";

interface Props {
  summary: PlayerSummary;
  playstyle: Playstyle;
}

export default function ReportHeader({ summary, playstyle }: Props) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {summary.username}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-foreground/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground/70">
            {platformLabel(summary.platform)}
          </span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${playstyleColor(
              playstyle.label
            )}`}
          >
            {playstyle.label}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm text-foreground/80 sm:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-foreground/50">Rating</p>
          <p className="font-semibold">{formatRating(summary.rating)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-foreground/50">Games</p>
          <p className="font-semibold">{summary.games_analyzed}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-foreground/50">Date range</p>
          <p className="font-semibold">{formatDateRange(summary.date_range)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-foreground/50">Time controls</p>
          <p className="font-semibold">{summary.time_class_mix}</p>
        </div>
      </div>
    </section>
  );
}
