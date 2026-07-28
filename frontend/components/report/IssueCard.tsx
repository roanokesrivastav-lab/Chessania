"use client";

import { useState } from "react";
import type { Issue } from "@/lib/types";
import { formatPlayedAt } from "@/lib/format";

function EmphasizedDiagnosis({ text }: { text: string }) {
  const parts = text.split(/(-?\d+(?:\.\d+)?%?)/g);
  return (
    <>
      {parts.map((part, i) =>
        /^-?\d+(?:\.\d+)?%?$/.test(part) ? (
          <span key={i} className="font-semibold text-foreground">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

interface Props {
  issue: Issue;
}

export default function IssueCard({ issue }: Props) {
  const [expanded, setExpanded] = useState(false);

  const impactColor =
    issue.rating_impact === "high"
      ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
      : issue.rating_impact === "medium"
      ? "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100"
      : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100";

  return (
    <article className="rounded-lg border border-foreground/10 bg-background p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="text-xl font-bold leading-tight text-foreground">
          {issue.headline}
        </h2>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${impactColor}`}
        >
          {issue.rating_impact}
        </span>
      </div>

      <p className="mt-2 text-foreground/80">
        <EmphasizedDiagnosis text={issue.diagnosis} />
      </p>

      <div className="mt-4 rounded-md bg-foreground/5 p-3">
        <p className="text-sm font-semibold text-foreground/90">Prescription</p>
        <p className="mt-1 text-sm text-foreground/80">{issue.prescription}</p>
        {issue.links.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {issue.links.map((link) => (
              <a
                key={link.url}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background transition-opacity hover:opacity-80"
              >
                {link.label}
              </a>
            ))}
          </div>
        )}
      </div>

      {issue.counter_evidence && (
        <p className="mt-3 text-xs italic text-foreground/60">
          Note: {issue.counter_evidence}
        </p>
      )}

      {issue.evidence.length > 0 && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="text-sm font-semibold text-foreground underline underline-offset-2"
          >
            {expanded ? "Hide" : "Show"} {issue.evidence.length} example
            {issue.evidence.length === 1 ? "" : "s"}
          </button>

          {expanded && (
            <ul className="mt-3 space-y-2">
              {issue.evidence.map((ev, i) => (
                <li key={i}>
                  <a
                    href={ev.game_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-md border border-foreground/10 p-3 transition-colors hover:bg-foreground/5"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-foreground/60">
                      <span>{formatPlayedAt(ev.played_at)}</span>
                      {ev.opponent_rating !== null && (
                        <span>vs {ev.opponent_rating}</span>
                      )}
                      <span>
                        · move {ev.ply} ({ev.move_san})
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-foreground/80">{ev.detail}</p>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}
