"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { analyze } from "@/lib/api";
import type { Platform } from "@/lib/types";

const PLATFORM_LABEL: Record<Platform, string> = {
  chesscom: "Chess.com",
  lichess: "Lichess",
};

const USERNAME_PATTERNS: Record<Platform, RegExp> = {
  chesscom: /^[a-zA-Z0-9_-]{3,25}$/,
  lichess: /^[a-zA-Z0-9_-]{2,30}$/,
};

export default function Home() {
  const router = useRouter();
  const [platform, setPlatform] = useState<Platform>("chesscom");
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateUsername = (value: string, forPlatform: Platform): string | null => {
    if (!value.trim()) {
      return "Please enter a username.";
    }
    if (!USERNAME_PATTERNS[forPlatform].test(value.trim())) {
      return `That doesn't look like a valid ${PLATFORM_LABEL[forPlatform]} username.`;
    }
    return null;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const validationError = validateUsername(username, platform);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const data = await analyze(platform, username.trim());
      router.push(`/analyzing/${data.job_id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <div className="flex max-w-md flex-col gap-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">
            Chessania
          </h1>
          <p className="text-lg text-foreground/80">
            Free coaching report from your last 20 games — no signup.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2">
            {(["chesscom", "lichess"] as Platform[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPlatform(p)}
                aria-pressed={platform === p}
                className={`rounded-lg border px-4 py-3 text-sm font-semibold transition-colors ${
                  platform === p
                    ? "border-foreground bg-foreground text-background"
                    : "border-foreground/20 bg-transparent text-foreground hover:border-foreground/40"
                }`}
              >
                {PLATFORM_LABEL[p]}
              </button>
            ))}
          </div>

          <div className="text-left">
            <label htmlFor="username" className="sr-only">
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="off"
              placeholder={`${PLATFORM_LABEL[platform]} username`}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              className="w-full rounded-lg border border-foreground/20 bg-background px-4 py-3 text-foreground placeholder:text-foreground/40 focus:border-foreground focus:outline-none focus:ring-2 focus:ring-foreground/20 disabled:opacity-60"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-200"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-foreground px-4 py-3 font-semibold text-background transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {loading ? "Waking up the engine…" : "Coach me"}
          </button>
        </form>

        <ul className="space-y-1 text-sm text-foreground/60">
          <li>Analyzes your last 20 rapid and blitz games with Stockfish.</li>
          <li>Built for sub-1800 players who want concrete, specific advice.</li>
          <li>Reports are public — share your link with anyone.</li>
        </ul>
      </div>
    </main>
  );
}
