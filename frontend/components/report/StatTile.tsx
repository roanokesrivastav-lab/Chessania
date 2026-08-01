import StatExplainer from "./StatExplainer";

interface Props {
  label: string;
  value: string;
  explainerId?: string;
}

/** A single stat tile (label + value + optional "?" explainer).
 *  Extracted from StatsBlock in S32 so the category dashboard and the
 *  Overall card reuse it. Numbers/formats unchanged. */
export default function StatTile({ label, value, explainerId }: Props) {
  return (
    <div className="rounded-lg border border-foreground/10 p-3">
      <p className="text-xs uppercase tracking-wide text-foreground/50">
        {label}
        {explainerId && <StatExplainer id={explainerId} />}
      </p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}
