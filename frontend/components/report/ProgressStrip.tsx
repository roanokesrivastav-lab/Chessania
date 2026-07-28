import type { Progress, Delta } from "@/lib/types";
import { formatNumber } from "@/lib/format";

interface Props {
  progress: Progress | null;
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {progress.vs_previous.length > 0 && (
          <DeltaGroup title="Since last report" deltas={progress.vs_previous} />
        )}
        {progress.vs_first.length > 0 && (
          <DeltaGroup title="Since first report" deltas={progress.vs_first} />
        )}
      </div>
      {progress.note && (
        <p className="mt-2 text-sm text-foreground/70">{progress.note}</p>
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
    <div className="rounded-lg border border-foreground/10 p-3">
      <h3 className="text-xs font-bold uppercase tracking-wide text-foreground/50">
        {title}
      </h3>
      <ul className="mt-2 space-y-1">
        {deltas.map((d) => (
          <li
            key={d.metric}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-foreground/80">{d.metric}</span>
            <span className="font-semibold">
              {formatNumber(d.previous)} → {formatNumber(d.current)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
