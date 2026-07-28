import type { StatsBlock as Stats } from "@/lib/types";
import { formatNumber, formatPercent, formatConversion, formatTrend } from "@/lib/format";
import StatExplainer from "./StatExplainer";

interface Props {
  stats: Stats;
}

export default function StatsBlock({ stats }: Props) {
  const byColor = stats.by_color;

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-bold uppercase tracking-wide text-foreground/60">
        Stats
      </h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Blunders/game" value={formatNumber(stats.blunders_per_game)} explainerId="blunders_per_game" />
        <Stat label="Mistakes/game" value={formatNumber(stats.mistakes_per_game)} explainerId="mistakes_per_game" />
        <Stat label="ACPL" value={formatNumber(stats.acpl_overall)} explainerId="acpl" />
        <Stat label="Endgame conversion" value={formatConversion(stats.endgame_conversion)} explainerId="endgame_conversion" />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Opening ACPL" value={formatNumber(stats.acpl_by_phase.opening)} explainerId="acpl_phase" />
        <Stat label="Middlegame ACPL" value={formatNumber(stats.acpl_by_phase.middlegame)} explainerId="acpl_phase" />
        <Stat label="Endgame ACPL" value={formatNumber(stats.acpl_by_phase.endgame)} explainerId="acpl_phase" />
      </div>

      <div className="rounded-lg border border-foreground/10 bg-foreground/5 p-3">
        <p className="text-xs uppercase tracking-wide text-foreground/50">
          Accuracy trend <StatExplainer id="accuracy_trend" />
        </p>
        <p className="mt-1 font-semibold">{formatTrend(stats.accuracy_trend)}</p>
      </div>

      {byColor && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wide text-foreground/50">
            By color
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Object.entries(byColor).map(([color, cs]) => (
              <div
                key={color}
                className="rounded-lg border border-foreground/10 p-3"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold capitalize">{color}</h4>
                  <span className="text-xs text-foreground/60">
                    {cs.games} game{cs.games === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-foreground/50">Blunders/game</p>
                    <p className="font-semibold">
                      {formatNumber(cs.blunders_per_game)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/50">ACPL</p>
                    <p className="font-semibold">
                      {cs.acpl_overall === null
                        ? "—"
                        : formatNumber(cs.acpl_overall)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/50">
                      Opening leak rate <StatExplainer id="opening_leak_rate" />
                    </p>
                    <p className="font-semibold">
                      {formatPercent(cs.opening_leak_rate)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-foreground/50">
                      Endgame conversion <StatExplainer id="endgame_conversion" />
                    </p>
                    <p className="font-semibold">
                      {formatConversion(cs.endgame_conversion)}
                    </p>
                  </div>
                </div>
                {cs.low_signal && (
                  <p className="mt-2 text-xs italic text-foreground/50">
                    Small sample — read lightly.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  explainerId,
}: {
  label: string;
  value: string;
  explainerId?: string;
}) {
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
