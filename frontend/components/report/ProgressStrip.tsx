import type { Progress as ProgressType, Delta } from "@/lib/types";
import {
  formatDeltaValue,
  directionArrow,
  directionColor,
  formatProgressDate,
} from "@/lib/format";

interface Props {
  progress: ProgressType | null;
}

export default function ProgressStrip({ progress }: Props) {
  if (!progress) return null;

  const hasDeltas =
    progress.vs_previous.length > 0 || progress.vs_first.length > 0;
  if (!hasDeltas) return null;

  return (
    <section>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-foreground/60">
        Progress
      </h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {progress.vs_previous.length > 0 && (
          <DeltaGroup
            title={`Since ${formatProgressDate(progress.previous_report_at)}`}
            deltas={progress.vs_previous}
          />
        )}
        {progress.vs_first.length > 0 && (
          <DeltaGroup title="Since first report" deltas={progress.vs_first} />
        )}
      </div>
      {progress.note && (
        <p className="mt-3 text-sm text-foreground/70">{progress.note}</p>
      )}
    </section>
  );
}

function DeltaGroup({
  title,
  deltas,
}: {
  title: string;
  deltas: Delta[];
}) {
  return (
    <div className="rounded-lg border border-foreground/10 p-4">
      <h3 className="text-xs font-bold uppercase tracking-wide text-foreground/50">
        {title}
      </h3>
      <ul className="mt-2 space-y-2">
        {deltas.map((d) => {
          const arrow = directionArrow(d.direction);
          const color = directionColor(d.direction);
          return (
            <li
              key={d.metric}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-foreground/80">{d.metric}</span>
              <span className="font-semibold">
                <span className={color}>{arrow}</span>{" "}
                <span className="tabular-nums text-foreground/90">
                  {formatDeltaValue(d.metric, d.previous)} →{" "}
                  {formatDeltaValue(d.metric, d.current)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
