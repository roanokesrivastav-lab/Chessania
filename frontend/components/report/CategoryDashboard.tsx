"use client";

import { useState } from "react";
import type { Report } from "@/lib/types";
import {
  orderCategories,
  issuesForCategory,
  headlineForCategory,
  tilesForCategory,
  verdictForCategory,
  unroutedIssues,
  type CategoryDef,
  type Verdict,
} from "@/lib/categories";
import IssueCard from "./IssueCard";
import OpeningPerformance from "./OpeningPerformance";
import StatTile from "./StatTile";
import StatsBlock from "./StatsBlock";

const VERDICT_LABEL: Record<Verdict, string> = {
  needs_work: "Needs work",
  strong: "Strong",
  solid: "Solid",
};

// Chip colors: needs_work is shaded by the severity of its worst fired issue.
const CHIP: Record<string, string> = {
  needs_work_high:
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
  needs_work_medium:
    "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100",
  needs_work_low:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
  strong:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100",
  solid: "bg-foreground/10 text-foreground",
};

function chipClass(verdict: Verdict, severity: string | null): string {
  if (verdict === "needs_work") {
    return CHIP[`needs_work_${severity}`] ?? CHIP.needs_work_medium;
  }
  return CHIP[verdict];
}

interface Props {
  report: Report;
}

/** Session 32: the report reorganized into a performance-by-category dashboard.
 *  Pure re-layout — every number is the same value/formatter as before. */
export default function CategoryDashboard({ report }: Props) {
  const ordered = orderCategories(report);
  const unrouted = unroutedIssues(report);

  return (
    <section aria-label="Performance by category" className="space-y-4">
      {ordered.map((def) => (
        <CategoryCard key={def.id} report={report} def={def} />
      ))}

      <div className="rounded-lg border border-foreground/10 bg-background p-4 shadow-sm">
        <StatsBlock stats={report.stats_block} />
        {unrouted.length > 0 && (
          <div className="mt-4 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wide text-foreground/50">
              Other
            </h3>
            {unrouted.map((issue) => (
              <IssueCard key={issue.key} issue={issue} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryCard({ report, def }: { report: Report; def: CategoryDef }) {
  const [open, setOpen] = useState(false);
  const { verdict, severity } = verdictForCategory(report, def);
  const headline = headlineForCategory(report, def);
  const tiles = tilesForCategory(report, def);
  const issues = issuesForCategory(report, def);
  const panelId = `category-${def.id}-panel`;
  const hasDetail =
    issues.length > 0 ||
    tiles.length > 0 ||
    (def.id === "opening" && report.opening_performance.length > 0);

  return (
    <section className="rounded-lg border border-foreground/10 bg-background shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-foreground/5 focus-visible:ring-2 focus-visible:ring-foreground/40 focus-visible:ring-offset-1"
      >
        <span className="text-lg font-bold text-foreground">{def.name}</span>
        <span className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${chipClass(
              verdict,
              severity
            )}`}
          >
            {VERDICT_LABEL[verdict]}
          </span>
          <span aria-hidden className="text-sm text-foreground/50">
            {open ? "▲" : "▼"}
          </span>
        </span>
      </button>

      {headline && (
        <div className="border-t border-foreground/10 p-4">
          <StatTile
            label={headline.label}
            value={headline.value}
            explainerId={headline.explainerId}
          />
        </div>
      )}

      {open && (
        <div
          id={panelId}
          role="region"
          aria-label={def.name}
          className={`space-y-4 p-4 ${
            headline ? "" : "border-t border-foreground/10"
          }`}
        >
          {def.id === "opening" && (
            <OpeningPerformance lines={report.opening_performance} />
          )}

          {issues.map((issue) => (
            <IssueCard key={issue.key} issue={issue} />
          ))}

          {tiles.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {tiles.map((tile) => (
                <StatTile
                  key={tile.label}
                  label={tile.label}
                  value={tile.value}
                  explainerId={tile.explainerId}
                />
              ))}
            </div>
          )}

          {!hasDetail && (
            <p className="text-sm text-foreground/60">
              Nothing flagged here — keep doing what you&apos;re doing.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
