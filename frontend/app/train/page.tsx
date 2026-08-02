"use client";
// V2-S12: Training Dashboard — home for /train. Composes existing
// pieces (categories.ts, trainerRouting.ts, getReport, fetchProgress)
// into a single-page view of what to drill and how you're doing.

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { getSession } from "@/lib/auth";
import type { SessionUser } from "@/lib/auth";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";
import {
  CATEGORIES,
  orderCategories,
  verdictForCategory,
  headlineForCategory,
  issuesForCategory,
  type CategoryDef,
} from "@/lib/categories";
import { trainerForIssue, type TrainerRoute } from "@/lib/trainerRouting";
import { fetchProgress, type TrainerProgress } from "@/lib/train";
import type { Delta } from "@/lib/types";

// ── localStorage key for persisting the picker ───────────────────────

const LS_KEY = "chessania_dashboard_player";

function loadSavedPlayer(): { platform: string; username: string } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed.platform && parsed.username) return parsed;
  } catch { /* corrupted */ }
  return null;
}

function savePlayer(platform: string, username: string) {
  try {
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({ platform, username })
    );
  } catch { /* quota exceeded, etc. */ }
}

// ── All live trainers (for the quick-link grid) ──────────────────────

interface TrainerLink {
  route: string;
  label: string;
  description: string;
  needsPlayer: boolean; // requires platform+username query params
}

const TRAINER_LINKS: TrainerLink[] = [
  { route: "/train/retry", label: "Retry Your Mistakes", description: "Replay your own blunder positions.", needsPlayer: true },
  { route: "/train/preventer", label: "Blunder Preventer", description: "Spot the threat and defend.", needsPlayer: true },
  { route: "/train/convert", label: "Advantage Capitalization", description: "Convert your winning positions vs the engine.", needsPlayer: true },
  { route: "/train/mate", label: "Checkmate Challenges", description: "Curated mate-in-N puzzles.", needsPlayer: false },
  { route: "/train/endgame", label: "Endgame Self-Tests", description: "Win or hold curated endgames.", needsPlayer: true },
];

// ── Helper: build a trainer deep-link with platform, username, games ─

function trainerDeepLink(
  trainer: string,
  platform: string,
  username: string,
  gameUrls: string[],
): string {
  const params = new URLSearchParams({
    platform,
    username,
  });
  if (gameUrls.length > 0) {
    params.set("games", gameUrls.join(","));
  }
  return `/train/${trainer}?${params.toString()}`;
}

// ── Severity badge ────────────────────────────────────────────────────

function SeverityBadge({ impact }: { impact: "high" | "medium" | "low" }) {
  const color =
    impact === "high" ? "var(--coral)" : impact === "medium" ? "var(--gold)" : "var(--green)";
  return (
    <span
      className="font-mono text-[0.6rem] uppercase tracking-widest font-bold"
      style={{ color }}
    >
      {impact}
    </span>
  );
}

// ── Verdict badge ─────────────────────────────────────────────────────

function VerdictBadge({ verdict }: { verdict: string }) {
  const color =
    verdict === "needs_work"
      ? "var(--coral)"
      : verdict === "strong"
        ? "var(--gold)"
        : "var(--green)";
  const label =
    verdict === "needs_work" ? "Needs work" : verdict === "strong" ? "Strong" : "Solid";
  return (
    <span
      className="font-mono text-[0.6rem] uppercase tracking-widest font-bold"
      style={{ color }}
    >
      {label}
    </span>
  );
}

// ── Card shell ────────────────────────────────────────────────────────

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[14px] border border-border bg-surface p-4 ${className}`}
    >
      {children}
    </div>
  );
}

// ── Inline player picker ─────────────────────────────────────────────

function PlayerPicker({
  onLoad,
  initial,
}: {
  onLoad: (p: string, u: string) => void;
  initial: { platform: string; username: string } | null;
}) {
  const [platform, setPlatform] = useState(initial?.platform ?? "chesscom");
  const [username, setUsername] = useState(initial?.username ?? "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;
    savePlayer(platform, username.trim());
    onLoad(platform, username.trim());
  };

  return (
    <Card>
      <h3 className="font-serif text-sm font-semibold text-fg mb-2">
        Your account
      </h3>
      <p className="text-xs text-fg-muted mb-3">
        Enter your Chess.com or Lichess username to see your report and drill queue.
      </p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg"
        >
          <option value="chesscom">Chess.com</option>
          <option value="lichess">Lichess</option>
        </select>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          className="flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg-muted/40 focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold/40"
        />
        <button
          type="submit"
          className="rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-bg transition-all hover:bg-gold/90"
        >
          Load
        </button>
      </form>
    </Card>
  );
}

// ── Weakness Scorecard ────────────────────────────────────────────────

function WeaknessScorecard({ report }: { report: Report }) {
  const ordered = orderCategories(report);

  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-serif text-lg font-semibold text-gold">
        Weakness Scorecard
      </h2>
      <div className="flex flex-col gap-1.5">
        {ordered.map((def) => {
          const { verdict, severity } = verdictForCategory(report, def);
          const headline = headlineForCategory(report, def);
          const fired = issuesForCategory(report, def);
          const hasTrainer = fired.some((i) => trainerForIssue(i.key) !== null);

          return (
            <div
              key={def.id}
              className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-fg">{def.name}</span>
                <span className="text-xs text-fg-muted">
                  {headline ? `${headline.value} ${headline.label}` : `No data`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {severity && <SeverityBadge impact={severity} />}
                <VerdictBadge verdict={verdict} />
                {hasTrainer && (
                  <a
                    href={`/train/${trainerForIssue(fired.find((i) => trainerForIssue(i.key) !== null)!.key)!.trainer}?platform=${encodeURIComponent(report.player_summary.platform)}&username=${encodeURIComponent(report.player_summary.username)}`}
                    className="rounded-md bg-gold/10 px-2 py-1 text-xs font-medium text-gold transition-colors hover:bg-gold/20"
                  >
                    Train
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Drill Queue ───────────────────────────────────────────────────────

function DrillQueue({
  report,
}: {
  report: Report;
}) {
  const platform = report.player_summary.platform;
  const username = report.player_summary.username;

  const queue = report.issues
    .filter((i) => trainerForIssue(i.key) !== null)
    .sort((a, b) => {
      const order = { high: 0, medium: 1, low: 2 };
      return (order[a.rating_impact] ?? 2) - (order[b.rating_impact] ?? 2);
    });

  if (queue.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-serif text-lg font-semibold text-gold">
        What to drill today
      </h2>
      <p className="text-xs text-fg-muted">
        Issues from your latest report that have a live trainer — ordered by
        impact.
      </p>
      <div className="flex flex-col gap-1.5">
        {queue.map((issue) => {
          const route = trainerForIssue(issue.key)!;
          const gameUrls = issue.evidence.map((e) => e.game_url);
          const link = trainerDeepLink(
            route.trainer,
            platform,
            username,
            gameUrls,
          );

          return (
            <div
              key={issue.key}
              className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-fg">
                  {issue.headline}
                </span>
                <span className="text-xs text-fg-muted">
                  {route.trainer} · {issue.evidence.length} game
                  {issue.evidence.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <SeverityBadge impact={issue.rating_impact} />
                <a
                  href={link}
                  className="rounded-md bg-gold px-2 py-1 text-xs font-semibold text-bg transition-colors hover:bg-gold/90"
                >
                  Train this
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Progress Panel ────────────────────────────────────────────────────

function ProgressPanel({ progress }: { progress: Record<string, TrainerProgress> | null }) {
  if (!progress) {
    return (
      <Card>
        <h3 className="font-serif text-sm font-semibold text-fg mb-1">
          Your Progress
        </h3>
        <p className="text-xs text-fg-muted">
          <a href="/login" className="text-gold underline hover:text-gold/80">
            Sign in
          </a>{" "}
          to track your progress and build streaks.
        </p>
      </Card>
    );
  }

  const trainers = Object.entries(progress);
  if (trainers.length === 0) {
    return (
      <Card>
        <h3 className="font-serif text-sm font-semibold text-fg mb-1">
          Your Progress
        </h3>
        <p className="text-xs text-fg-muted">
          No training attempts yet — start drilling above!
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="font-serif text-sm font-semibold text-fg mb-3">
        Your Progress
      </h3>
      <div className="flex flex-col gap-2">
        {trainers.map(([trainer, stats]) => (
          <div
            key={trainer}
            className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2"
          >
            <span className="text-sm font-medium text-fg capitalize">
              {trainer}
            </span>
            <div className="flex items-center gap-3 text-xs font-mono text-fg-muted">
              <span>{stats.attempts} attempts</span>
              <span style={{ color: "var(--gold)" }}>{stats.perfect}P</span>
              <span style={{ color: "var(--green)" }}>{stats.pass}P</span>
              <span style={{ color: "var(--coral)" }}>{stats.fail}F</span>
              {stats.current_streak > 0 && (
                <span className="text-gold">🔥{stats.current_streak}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── V2-S13: Trainer → Delta metric mapping ──────────────────────────

const TRAINER_METRIC_MAP: Record<string, string[]> = {
  retry: ["Blunders/game"],
  preventer: ["Blunders/game"],
  endgame: ["Endgame conversion"],
  // convert, mate → no Delta metric (show count only, no movement claim)
};

function directionArrow(dir: string): string {
  if (dir === "better") return "↑";
  if (dir === "worse") return "↓";
  return "→";
}

function directionColor(dir: string): string {
  if (dir === "better") return "var(--green)";
  if (dir === "worse") return "var(--coral)";
  return "var(--fg-muted)";
}

// ── "Is it working?" section ────────────────────────────────────────

function IsItWorking({
  report,
  user,
}: {
  report: Report | null;
  user: SessionUser | null;
}) {
  const [sinceProgress, setSinceProgress] = useState<Record<string, TrainerProgress> | null>(null);
  const [deltaLoading, setDeltaLoading] = useState(false);

  useEffect(() => {
    if (!report?.progress || !user) return;
    setDeltaLoading(true);
    fetchProgress(report.progress.previous_report_at)
      .then((p) => setSinceProgress(p))
      .finally(() => setDeltaLoading(false));
  }, [report?.progress?.previous_report_at, user]);

  // Guest → sign-in + re-analyze nudge.
  if (!user) {
    return (
      <Card>
        <h3 className="font-serif text-sm font-semibold text-fg mb-1">
          Is it working?
        </h3>
        <p className="text-xs text-fg-muted">
          <a href="/login" className="text-gold underline hover:text-gold/80">
            Sign in
          </a>{" "}
          and re-analyze your games to see whether your training correlates with
          real improvement.
        </p>
      </Card>
    );
  }

  // No report loaded yet.
  if (!report) return null;

  // First/only report → honest re-analyze prompt.
  if (!report.progress) {
    return (
      <Card>
        <h3 className="font-serif text-sm font-semibold text-fg mb-1">
          Is it working?
        </h3>
        <p className="text-xs text-fg-muted">
          Re-analyze after playing a few more games to measure whether your
          training is working — a single report has nothing to compare against.
        </p>
      </Card>
    );
  }

  const deltas = report.progress.vs_previous;
  const note = report.progress.note;

  // Build trainer counts for the since-last-report period.
  const trainerCounts: Record<string, number> = {};
  if (sinceProgress) {
    for (const [trainer, stats] of Object.entries(sinceProgress)) {
      trainerCounts[trainer] = stats.attempts;
    }
  }

  // Build correlation lines.
  const correlationLines: { metric: string; delta: Delta; trainers: string[]; count: number }[] = [];
  const unmatchedDeltas: Delta[] = [];

  for (const delta of deltas) {
    const matchingTrainers: string[] = [];
    for (const [trainer, metrics] of Object.entries(TRAINER_METRIC_MAP)) {
      if (metrics.includes(delta.metric)) {
        matchingTrainers.push(trainer);
      }
    }
    if (matchingTrainers.length > 0) {
      const count = matchingTrainers.reduce((sum, t) => sum + (trainerCounts[t] ?? 0), 0);
      correlationLines.push({ metric: delta.metric, delta, trainers: matchingTrainers, count });
    } else {
      unmatchedDeltas.push(delta);
    }
  }

  // Convert/mate: show count, no movement claim.
  const untrackedTrainers = ["convert", "mate"]
    .filter((t) => (trainerCounts[t] ?? 0) > 0);

  return (
    <Card>
      <h3 className="font-serif text-sm font-semibold text-fg mb-2">
        Is it working?
      </h3>

      {deltaLoading && <p className="text-xs text-fg-muted">Loading drill counts…</p>}

      {/* Correlation lines */}
      {!deltaLoading && correlationLines.length === 0 && unmatchedDeltas.length === 0 && untrackedTrainers.length === 0 && (
        <p className="text-xs text-fg-muted">
          Train some drills and re-analyze to see whether your practice
          correlates with improvement.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {correlationLines.map(({ metric, delta, trainers, count }) => (
          <div
            key={metric}
            className="rounded-lg border border-border bg-surface-2 px-3 py-2"
          >
            <p className="text-xs text-fg-muted leading-relaxed">
              You trained{" "}
              <strong className="text-fg">
                {trainers.join(" / ")}
              </strong>{" "}
              <strong className="text-fg">{count}×</strong>{" "}
              since your last report. Meanwhile{" "}
              <strong className="text-fg">{metric}</strong>{" "}
              went{" "}
              <span className="font-mono">
                {delta.previous.toFixed(1)} → {delta.current.toFixed(1)}
              </span>{" "}
              <span
                className="font-bold"
                style={{ color: directionColor(delta.direction) }}
              >
                {directionArrow(delta.direction)}
              </span>
              .
            </p>
          </div>
        ))}

        {/* Untracked metric deltas (no trainer) — show movement only. */}
        {unmatchedDeltas.map((delta) => (
          <div
            key={delta.metric}
            className="rounded-lg border border-border bg-surface-2 px-3 py-2"
          >
            <p className="text-xs text-fg-muted leading-relaxed">
              Meanwhile{" "}
              <strong className="text-fg">{delta.metric}</strong>{" "}
              went{" "}
              <span className="font-mono">
                {delta.previous.toFixed(1)} → {delta.current.toFixed(1)}
              </span>{" "}
              <span
                className="font-bold"
                style={{ color: directionColor(delta.direction) }}
              >
                {directionArrow(delta.direction)}
              </span>
              .
            </p>
          </div>
        ))}

        {/* Untracked trainers (convert/mate) — count only, no claim. */}
        {untrackedTrainers.map((trainer) => (
          <div
            key={trainer}
            className="rounded-lg border border-border bg-surface-2 px-3 py-2"
          >
            <p className="text-xs text-fg-muted leading-relaxed">
              You trained{" "}
              <strong className="text-fg capitalize">{trainer}</strong>{" "}
              <strong className="text-fg">{trainerCounts[trainer]}×</strong>{" "}
              since your last report. (No matching report metric — keep practicing!)
            </p>
          </div>
        ))}
      </div>

      {/* Honesty hedge — always show the note when present. */}
      {note && (
        <p className="mt-3 text-xs leading-relaxed" style={{ color: "var(--gold)" }}>
          ⚠ {note}
        </p>
      )}

      {/* Never claim causation. */}
      <p className="mt-2 text-[0.65rem] text-fg-muted/60 leading-relaxed">
        Correlation is not causation — these numbers describe what happened, not
        why. Keep drilling and re-analyzing to build a real picture over time.
      </p>
    </Card>
  );
}

// ── Trainer Grid ──────────────────────────────────────────────────────

function TrainerGrid({ platform, username }: { platform?: string; username?: string }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-serif text-lg font-semibold text-gold">
        All Trainers
      </h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {TRAINER_LINKS.map((t) => {
          const href = t.needsPlayer && platform && username
            ? `/train/${t.route.split("/").pop()}?platform=${encodeURIComponent(platform)}&username=${encodeURIComponent(username)}`
            : t.route;
          return (
            <a
              key={t.route}
              href={href}
              className="rounded-lg border border-border bg-surface-2 px-4 py-3 transition-colors hover:border-gold/50"
            >
              <span className="text-sm font-medium text-fg block">
                {t.label}
              </span>
              <span className="text-xs text-fg-muted">{t.description}</span>
            </a>
          );
        })}
      </div>
      <a
        href="/duel"
        className="rounded-lg border border-border bg-surface-2 px-4 py-3 transition-colors hover:border-gold/50 text-center"
      >
        <span className="text-sm font-medium text-fg">Position Duels</span>
        <span className="block text-xs text-fg-muted">
          Create Lichess challenges from any position.
        </span>
      </a>
    </section>
  );
}

// ── Page ─────────────────────────────────────────────────────────────

export default function TrainPage() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [player, setPlayer] = useState<{
    platform: string;
    username: string;
  } | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [progress, setProgress] = useState<Record<string, TrainerProgress> | null>(null);

  // Load saved player + auth on mount.
  useEffect(() => {
    const saved = loadSavedPlayer();
    if (saved) {
      setPlayer(saved);
      loadReport(saved.platform, saved.username);
    }
    getSession().then((s) => setUser(s.user));
  }, []);

  // Load progress when signed in.
  useEffect(() => {
    if (user) {
      fetchProgress().then((p) => setProgress(p));
    }
  }, [user]);

  const loadReport = useCallback(
    async (platform: string, username: string) => {
      setReportError(null);
      setReportLoading(true);
      try {
        const r = await getReport(platform as "chesscom" | "lichess", username);
        setReport(r);
      } catch (err) {
        setReport(null);
        setReportError(
          err instanceof Error ? err.message : "Could not load report.",
        );
      } finally {
        setReportLoading(false);
      }
    },
    [],
  );

  const handlePlayerLoad = (platform: string, username: string) => {
    setPlayer({ platform, username });
    loadReport(platform, username);
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-10">
      {/* Header */}
      <section className="flex flex-col gap-2">
        <h1 className="font-serif text-3xl font-bold tracking-tight text-gold">
          Training
        </h1>
        <p className="text-sm leading-relaxed text-fg-muted">
          Drill your own mistakes, test yourself on set positions, or duel a
          friend from a custom position.
        </p>
      </section>

      {/* Player picker or report-based sections */}
      {!player ? (
        <PlayerPicker onLoad={handlePlayerLoad} initial={null} />
      ) : (
        <>
          {/* Change player */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-fg-muted">
              {player.username} ({player.platform})
            </span>
            <button
              type="button"
              onClick={() => {
                setPlayer(null);
                setReport(null);
                setReportError(null);
              }}
              className="text-xs text-fg-muted underline hover:text-fg"
            >
              Change
            </button>
          </div>

          {/* Loading / error */}
          {reportLoading && (
            <p className="text-sm text-fg-muted">Loading report…</p>
          )}
          {reportError && (
            <p className="text-sm text-coral">{reportError}</p>
          )}

          {/* Report-based sections */}
          {report && (
            <>
              <WeaknessScorecard report={report} />
              <DrillQueue report={report} />
            </>
          )}
        </>
      )}

      {/* Progress (always visible; nudge for guests) */}
      <ProgressPanel progress={progress} />

      {/* V2-S13: Is it working? */}
      <IsItWorking report={report} user={user} />

      {/* Trainer grid */}
      <TrainerGrid
        platform={player?.platform}
        username={player?.username}
      />
    </main>
  );
}
