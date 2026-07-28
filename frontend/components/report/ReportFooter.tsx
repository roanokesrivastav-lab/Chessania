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
}

export default function ReportFooter({
  platform,
  username,
  games_analyzed,
  engine_depth,
  generated_at,
}: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const publicUrl =
    typeof window !== "undefined" ? window.location.href : "";

  const handleReanalyze = async () => {
    setError(null);
    setLoading(true);
    try {
      const data = await analyze(platform, username);
      router.push(`/analyzing/${data.job_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setLoading(false);
    }
  };

  return (
    <footer className="space-y-3 border-t border-foreground/10 pt-6 text-sm text-foreground/70">
      <p>
        Analyzed {games_analyzed} games at depth {engine_depth}. Report
        generated on {new Date(generated_at).toLocaleDateString()}.
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

      <button
        onClick={handleReanalyze}
        disabled={loading}
        className="rounded-lg bg-foreground px-4 py-2 font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {loading ? "Starting…" : "Re-analyze"}
      </button>
    </footer>
  );
}
