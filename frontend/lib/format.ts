import type { Platform } from "./types";

export function formatNumber(value: number | null, fallback = "—"): string {
  if (value === null || Number.isNaN(value)) return fallback;
  // Mirror the raw stored value as closely as possible (no extra rounding)
  return String(value);
}

export function formatPercent(value: number | null, fallback = "—"): string {
  if (value === null || Number.isNaN(value)) return fallback;
  // opening_leak_rate is a 0-1 fraction (features.py: leak_count / len(games),
  // e.g. 0.1 = 10%); display as a percent. Do NOT remove the ×100 — see S20/S21 log.
  return `${formatNumber(value * 100)}%`;
}

export function formatConversion(value: number | null, fallback = "—"): string {
  if (value === null || Number.isNaN(value)) return fallback;
  // endgame_conversion is stored as a 0-1 fraction (e.g. 0.55); display as 55%
  return `${formatNumber(value * 100)}%`;
}

export function formatDateRange(value: string | null): string {
  if (!value) return "—";
  return value;
}

export function formatRating(value: number | null): string {
  if (value === null) return "unrated";
  return `${value}`;
}

export function formatPlayedAt(iso: string | null): string {
  if (!iso) return "Unknown date";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

const TREND_TEXT: Record<string, string> = {
  improving: "↑ improving",
  flat: "→ flat",
  declining: "↓ declining",
  insufficient_data: "not enough games yet",
};

export function formatTrend(value: string): string {
  return TREND_TEXT[value] ?? value;
}

export function playstyleColor(label: string): string {
  switch (label) {
    case "tactical":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100";
    case "positional":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100";
    case "balanced":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100";
    default:
      return "bg-foreground/10 text-foreground";
  }
}

export function platformLabel(platform: Platform): string {
  return platform === "chesscom" ? "Chess.com" : "Lichess";
}

export function platformUrlPrefix(platform: Platform): string {
  return platform === "chesscom"
    ? "https://www.chess.com/member/"
    : "https://lichess.org/@/";
}

export function formatDeltaValue(metricLabel: string, value: number): string {
  if (metricLabel.toLowerCase().includes("conversion")) {
    return `${Math.round(value * 100)}%`;
  }
  if (metricLabel.toLowerCase().includes("acpl")) {
    return `${Math.round(value)}`;
  }
  // Blunders/game and fallback: one decimal.
  return `${value.toFixed(1)}`;
}

export function directionArrow(direction: "better" | "worse" | "flat"): string {
  if (direction === "better") return "↑";
  if (direction === "worse") return "↓";
  return "→";
}

export function directionColor(direction: "better" | "worse" | "flat"): string {
  if (direction === "better") return "text-emerald-600 dark:text-emerald-400";
  if (direction === "worse") return "text-rose-600 dark:text-rose-400";
  return "text-foreground/50";
}

export function formatProgressDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
