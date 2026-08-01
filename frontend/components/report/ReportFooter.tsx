"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { analyze } from "@/lib/api";
import type { Platform } from "@/lib/types";

interface Props {
  platform: Platform;
  username: string;
  games_analyzed: number;
  engine_depth: number;
  generated_at: string;
  // S33: old stored reports have no mode — treat as standard when absent.
  analysis_mode?: "standard" | "deep";
}

export default function ReportFooter({
  platform,
  username,
  games_analyzed,
  engine_depth,
  generated_at,
  analysis_mode,
}: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const publicUrl =
    typeof window !== "undefined" ? window.location.href : "";

  const startAnalysis = async (mode: "standard" | "deep") => {
    setError(null);
    setLoading(true);
    try {
      const data = await analyze(platform, username, mode);
      router.push(`/analyzing/${data.job_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setLoading(false);
    }
  };

  const isDeep = analysis_mode === "deep";

  return (
    <footer className="space-y-3 border-t border-foreground/10 pt-6 text-sm text-foreground/70">
      <p>
        {isDeep ? "Deep analysis of" : "Analyzed"} {games_analyzed} games at
        depth {engine_depth}. Report generated on{" "}
        {new Date(generated_at).toLocaleDateString()}.
      </p>
      <p className="break-words">
        Reports are public at{" "}
        <a
          href={publicUrl || "#"}
          className="text-foreground underline underline-offset-2"
          suppressHydrationWarning
        >
          this link
        </a>
        .
      </p>

      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => startAnalysis("standard")}
          disabled={loading}
          className="rounded-lg bg-foreground px-4 py-2 font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {loading ? "Starting…" : "Re-analyze"}
        </button>
        <button
          onClick={() => startAnalysis("deep")}
          disabled={loading}
          className="rounded-lg border border-foreground/30 px-4 py-2 font-semibold text-foreground transition-colors hover:bg-foreground/5 disabled:opacity-60"
        >
          {loading ? "Starting…" : "Deep dive (~100 games)"}
        </button>
      </div>
    </footer>
  );
}
