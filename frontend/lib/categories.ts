import type { Issue, Report, Strength } from "@/lib/types";
import { formatConversion, formatNumber } from "@/lib/format";

/**
 * Performance-by-category map (Session 32) — the single source of truth.
 *
 * Every issue key the backend can emit routes to EXACTLY one category
 * (all 15 keys below; see ALL_ISSUE_KEYS). This is presentation-only:
 * it re-lays-out numbers the report already carries, never invents them.
 */

export type CategoryId =
  | "opening"
  | "tactics"
  | "advantage"
  | "resourcefulness"
  | "time"
  | "endgame";

export type Impact = "high" | "medium" | "low";
export type Verdict = "needs_work" | "strong" | "solid";

export interface CategoryDef {
  id: CategoryId;
  name: string;
  issueKeys: string[];
}

export const CATEGORIES: CategoryDef[] = [
  {
    id: "opening",
    name: "Opening",
    issueKeys: ["opening_leak", "opening_general", "opening_variation"],
  },
  {
    id: "tactics",
    name: "Tactics & Blunders",
    issueKeys: ["blunder_rate", "hung_pieces", "tilt", "overextension"],
  },
  {
    id: "advantage",
    name: "Advantage Capitalization",
    issueKeys: ["advantage_capitalization"],
  },
  {
    id: "resourcefulness",
    name: "Resourcefulness",
    issueKeys: ["missed_saves"],
  },
  {
    id: "time",
    name: "Time Management",
    issueKeys: [
      "rushed_blunders",
      "time_trouble_collapse",
      "dawdling",
      "blitz_gap",
    ],
  },
  {
    id: "endgame",
    name: "Endgame",
    issueKeys: ["endgame_conversion", "late_collapse"],
  },
];

/** All 15 issue keys the map routes. Every one must appear in exactly one category. */
export const ALL_ISSUE_KEYS: string[] = CATEGORIES.flatMap((c) => c.issueKeys);

const ISSUE_TO_CATEGORY = new Map<string, CategoryId>(
  CATEGORIES.flatMap((c) => c.issueKeys.map((k) => [k, c.id] as const))
);

export function categoryForIssue(key: string): CategoryId | null {
  return ISSUE_TO_CATEGORY.get(key) ?? null;
}

export function issuesForCategory(report: Report, def: CategoryDef): Issue[] {
  return report.issues.filter((i) => def.issueKeys.includes(i.key));
}

/** Safety net: issues the map doesn't know about (a future backend key)
 *  still render, under the Overall card, so nothing is ever silently dropped. */
export function unroutedIssues(report: Report): Issue[] {
  return report.issues.filter((i) => categoryForIssue(i.key) === null);
}

// ---------------------------------------------------------------------------
// Verdicts (deterministic, display-only — never a composite score)
// ---------------------------------------------------------------------------

const SEVERITY_RANK: Record<Impact, number> = { high: 0, medium: 1, low: 2 };

/**
 * "Strong" thresholds for the natural rate categories, mirroring backend config
 * (backend/app/config.py). IMPORTANT: if you tune those thresholds, mirror the
 * new values here or the verdict drifts (same caveat as OpeningPerformance.tsx).
 */
const RATE_STRONG_THRESHOLD: Partial<Record<CategoryId, number>> = {
  endgame: 0.6, // COACH_ENDGAME_CONVERSION — the 0.60 gate
  advantage: 0.6, // COACH_ADVANTAGE_CAPITALIZATION
  resourcefulness: 0.4, // COACH_RESOURCEFULNESS
};

/**
 * Strength → category keywords, from the actual strength copy in
 * backend/app/coach.py `_strength_for`. Display-only classification:
 * the contract's Strength carries no category field, so we match on copy.
 * A phase strength ("Your middlegame is genuinely solid.") lands on the
 * closest category; "accuracy trending up" is cross-cutting (Overall).
 * IMPORTANT: if coach.py copy is ever reworded, re-check these keywords
 * or a "Strong" verdict will silently flip (same caveat as the thresholds).
 */
const STRENGTH_KEYWORDS: Partial<Record<CategoryId, string[]>> = {
  resourcefulness: ["fight back from losing", "resilience"],
  endgame: ["convert winning endgame", "your endgame is"],
  time: ["time control", "cleanest time"],
  opening: ["your opening is"],
  tactics: ["your middlegame is"],
  advantage: [],
};

export interface CategoryVerdict {
  verdict: Verdict;
  /** Severity of the worst fired issue (null when the verdict isn't needs_work). */
  severity: Impact | null;
}

export function verdictForCategory(
  report: Report,
  def: CategoryDef
): CategoryVerdict {
  const fired = issuesForCategory(report, def);
  if (fired.length > 0) {
    const worst = fired.reduce((a, b) =>
      SEVERITY_RANK[a.rating_impact] <= SEVERITY_RANK[b.rating_impact] ? a : b
    );
    return { verdict: "needs_work", severity: worst.rating_impact };
  }

  const rate = rateForCategory(report, def);
  const threshold = RATE_STRONG_THRESHOLD[def.id];
  const rateStrong = threshold !== undefined && rate !== null && rate >= threshold;
  if (strengthMatchesCategory(report.strengths, def) || rateStrong) {
    return { verdict: "strong", severity: null };
  }
  return { verdict: "solid", severity: null };
}

function rateForCategory(report: Report, def: CategoryDef): number | null {
  switch (def.id) {
    case "endgame":
      return report.stats_block.endgame_conversion;
    case "advantage":
      return report.stats_block.advantage_capitalization;
    case "resourcefulness":
      return report.stats_block.resourcefulness;
    default:
      return null;
  }
}

function strengthMatchesCategory(
  strengths: Strength[],
  def: CategoryDef
): boolean {
  const keywords = STRENGTH_KEYWORDS[def.id];
  if (!keywords || keywords.length === 0) return false;
  const text = strengths
    .map((s) => `${s.headline} ${s.detail}`)
    .join(" ")
    .toLowerCase();
  return keywords.some((k) => text.includes(k.toLowerCase()));
}

// ---------------------------------------------------------------------------
// Headline number + detail tiles (re-layout only — same formatters as before)
// ---------------------------------------------------------------------------

export interface Headline {
  label: string;
  value: string;
  /** Keeps the S27 "?" explainer next to the number (rendered as a StatTile). */
  explainerId?: string;
}

/** The real key number for a category's card, or null (verdict only).
 *  Never a composite % — Opening/Tactics/Time show a real number or nothing. */
export function headlineForCategory(
  report: Report,
  def: CategoryDef
): Headline | null {
  const stats = report.stats_block;
  switch (def.id) {
    case "tactics":
      return {
        label: "Blunders/game",
        value: formatNumber(stats.blunders_per_game),
        explainerId: "blunders_per_game",
      };
    case "advantage":
      if (stats.advantage_capitalization === null) return null;
      return {
        label: "Advantage conversion",
        value: formatConversion(stats.advantage_capitalization),
        explainerId: "advantage_capitalization",
      };
    case "resourcefulness":
      if (stats.resourcefulness === null) return null;
      return {
        label: "Resourcefulness",
        value: formatConversion(stats.resourcefulness),
        explainerId: "resourcefulness",
      };
    case "endgame":
      if (stats.endgame_conversion === null) return null;
      return {
        label: "Endgame conversion",
        value: formatConversion(stats.endgame_conversion),
        explainerId: "endgame_conversion",
      };
    case "opening": {
      // opening_performance was added in S31 — a report generated before then
      // (an older stored JSON) won't carry it, so guard against undefined
      // rather than crash on `.length` (this runs for the report page AND the
      // V2-S12 dashboard, both of which may read an old stored report).
      const lines = report.opening_performance ?? [];
      if (lines.length === 0) return null;
      return {
        label: "Variations tracked",
        value: String(lines.length),
      };
    }
    default:
      return null; // time: verdict only
  }
}

export interface StatTileSpec {
  label: string;
  value: string;
  explainerId?: string;
}

/** Extra stat tiles shown in a category's expanded detail (headline already
 *  shown collapsed; these carry the S27 "?" explainers). */
export function tilesForCategory(
  report: Report,
  def: CategoryDef
): StatTileSpec[] {
  if (def.id === "tactics") {
    return [
      {
        label: "Mistakes/game",
        value: formatNumber(report.stats_block.mistakes_per_game),
        explainerId: "mistakes_per_game",
      },
    ];
  }
  return [];
}

// ---------------------------------------------------------------------------
// Concern ordering ("what to fix first"): high-impact fired issues first,
// then by severity, then the stable map order for ties.
// ---------------------------------------------------------------------------

export function orderCategories(report: Report): CategoryDef[] {
  return CATEGORIES.map((def, index) => ({ def, index }))
    .sort(
      (a, b) =>
        concernRank(report, a.def) - concernRank(report, b.def) ||
        a.index - b.index
    )
    .map(({ def }) => def);
}

function concernRank(report: Report, def: CategoryDef): number {
  const fired = issuesForCategory(report, def);
  if (fired.length === 0) return 3; // no fired issue → after every problem category
  return Math.min(...fired.map((i) => SEVERITY_RANK[i.rating_impact]));
}
