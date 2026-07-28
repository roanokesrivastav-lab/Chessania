"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, getJob } from "@/lib/api";
import type { Job, JobStage } from "@/lib/types";

const WAITING_LINES = [
  "Teaching the engine your favorite squares…",
  "Counting tactics and missed forks…",
  "Reading between the moves…",
  "Finding the exact moment each game slipped…",
  "Polishing advice you can actually use…",
];

const STAGE_COPY: Record<JobStage, string> = {
  fetching: "Pulling your recent games…",
  analyzing: "Analyzing game",
  coaching: "Writing your report…",
};

function formatStageText(job: Job): string {
  if (job.state === "done") return "Done — taking you to your report…";
  if (job.state === "error") return "Analysis failed";
  if (job.stage === "analyzing") {
    const total = Math.max(job.total_games, 1);
    const current = Math.min(job.current_game, total);
    return `Analyzing game ${current} of ${total}`;
  }
  return STAGE_COPY[job.stage] ?? "Working…";
}

export default function AnalyzingPage() {
  const router = useRouter();
  const { jobId } = useParams<{ jobId: string }>();

  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [is404, setIs404] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [waitingLineIndex, setWaitingLineIndex] = useState(0);

  const stoppedRef = useRef(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const missCountRef = useRef(0);
  const nextPollAfterRef = useRef<number>(0);

  // Poll immediately, then every 2 seconds. Stop when the job is terminal.
  useEffect(() => {
    stoppedRef.current = false;

    async function poll() {
      if (stoppedRef.current) return;
      if (Date.now() < nextPollAfterRef.current) return;

      try {
        const data = await getJob(jobId);
        if (stoppedRef.current) return;

        missCountRef.current = 0;
        nextPollAfterRef.current = 0;
        setReconnecting(false);
        setJob(data);

        if (data.state === "done") {
          clearPolling();
          router.replace(`/r/${data.platform}/${data.username}`);
          return;
        }

        if (data.state === "error") {
          clearPolling();
          setError(data.error_message ?? "Analysis failed.");
          return;
        }
      } catch (err) {
        if (stoppedRef.current) return;

        if (err instanceof ApiError && err.status === 404) {
          clearPolling();
          setIs404(true);
          return;
        }

        missCountRef.current += 1;
        if (missCountRef.current >= 3) {
          setReconnecting(true);
        }

        // Modest backoff: 2s, 4s, 8s, capped at 10s.
        const backoff = Math.min(
          2000 * 2 ** (missCountRef.current - 1),
          10000
        );
        nextPollAfterRef.current = Date.now() + backoff;
      }
    }

    function clearPolling() {
      stoppedRef.current = true;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      if (lineIntervalRef.current) {
        clearInterval(lineIntervalRef.current);
        lineIntervalRef.current = null;
      }
    }

    poll();
    pollIntervalRef.current = setInterval(poll, 2000);

    // Cleanup: clear the interval when the component unmounts or the job
    // reaches a terminal state so we don't keep polling off-screen.
    return () => clearPolling();
  }, [jobId, router]);

  // Rotate a playful waiting line every 4 seconds while the job is running.
  // The interval is cleared on terminal state or unmount.
  useEffect(() => {
    lineIntervalRef.current = setInterval(() => {
      if (stoppedRef.current) {
        if (lineIntervalRef.current) {
          clearInterval(lineIntervalRef.current);
          lineIntervalRef.current = null;
        }
        return;
      }
      setWaitingLineIndex((prev) => (prev + 1) % WAITING_LINES.length);
    }, 4000);

    return () => {
      if (lineIntervalRef.current) {
        clearInterval(lineIntervalRef.current);
        lineIntervalRef.current = null;
      }
    };
  }, []);

  const progress =
    job && job.total_games > 0
      ? Math.min(job.current_game / job.total_games, 1)
      : 0;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <div className="flex w-full max-w-md flex-col gap-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {job ? formatStageText(job) : "Starting…"}
        </h1>

        {job && job.state !== "error" && job.state !== "done" && (
          <div className="w-full">
            {job.stage !== "fetching" && (
              <div className="mb-2 h-3 w-full overflow-hidden rounded-full bg-foreground/10">
                <div
                  className="h-full rounded-full bg-foreground transition-all duration-500"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
            )}
            <p className="text-sm text-foreground/70">
              {WAITING_LINES[waitingLineIndex]}
            </p>
          </div>
        )}

        {reconnecting && (
          <p className="text-sm text-amber-600 dark:text-amber-400">
            Reconnecting…
          </p>
        )}

        {(error || is404) && (
          <div className="flex flex-col gap-3 rounded-lg bg-red-50 px-4 py-3 text-red-700 dark:bg-red-950 dark:text-red-200">
            <p>{error ?? "That analysis expired — start a fresh one."}</p>
            <Link
              href="/"
              className="font-semibold underline underline-offset-2"
            >
              Try another username
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
