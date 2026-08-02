"use client";
// V2-S10: Position Duels — create a Lichess challenge from a FEN,
// get per-color share-links back, hand them out to two players.
// No realtime code on our side — the game lives entirely on Lichess.

import { useCallback, useState } from "react";
import { parseFen } from "chessops/fen";

import Board from "@/components/board/Board";
import { createDuel, type DuelResponse } from "@/lib/duels";
import { MATE_SET } from "@/lib/mateSet";
import { ENDGAME_SET } from "@/lib/endgameSet";

// ── Types ────────────────────────────────────────────────────────────

type DuelMode = "realtime" | "correspondence";
type PositionSource = "paste" | "curated-mate" | "curated-endgame";

// ── Curated positions for quick-pick ─────────────────────────────────

interface CuratedOption {
  id: string;
  fen: string;
  label: string;
  source: "curated-mate" | "curated-endgame";
}

const CURATED_OPTIONS: CuratedOption[] = [
  ...MATE_SET.map((m) => ({
    id: m.id,
    fen: m.fen,
    label: `${m.pattern} (Mate in ${m.mateInN})`,
    source: "curated-mate" as const,
  })),
  ...ENDGAME_SET.map((e) => ({
    id: e.id,
    fen: e.fen,
    label: `${e.pattern} (${e.target === "win" ? "Win" : "Hold"})`,
    source: "curated-endgame" as const,
  })),
];

// ── Page ─────────────────────────────────────────────────────────────

export default function DuelPage() {
  const [fen, setFen] = useState("");
  const [fenError, setFenError] = useState<string | null>(null);
  const [mode, setMode] = useState<DuelMode>("realtime");
  const [source, setSource] = useState<PositionSource>("paste");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DuelResponse | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  // Validate FEN on every keystroke for the paste tab.
  const validateFen = useCallback((value: string) => {
    if (!value.trim()) {
      setFenError(null);
      return;
    }
    const parsed = parseFen(value.trim());
    if (parsed.isErr) {
      setFenError("That doesn't look like a valid FEN — check the format.");
    } else {
      setFenError(null);
    }
  }, []);

  const handleFenChange = (value: string) => {
    setFen(value);
    validateFen(value);
  };

  const handlePickCurated = (option: CuratedOption) => {
    setFen(option.fen);
    setSource(option.source);
    setFenError(null);
    setError(null);
    setResult(null);
  };

  const handlePasteTab = () => {
    setSource("paste");
    setResult(null);
    setError(null);
  };

  const handleCreate = async () => {
    setError(null);
    setResult(null);

    const trimmed = fen.trim();
    if (!trimmed) {
      setError("Please enter a FEN or pick a curated position.");
      return;
    }

    const parsed = parseFen(trimmed);
    if (parsed.isErr) {
      setError("That position doesn't look valid — check the FEN and try again.");
      return;
    }

    setLoading(true);
    try {
      const duel = await createDuel({
        fen: trimmed,
        source,
        mode,
      });
      setResult(duel);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong — try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Fallback for non-HTTPS localhost.
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  const handleSwapAndReplay = () => {
    setResult(null);
    // Keep the same FEN and mode — just clear the result so the user
    // can create a fresh duel from the same position.
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-10">
      {/* Header */}
      <section className="flex flex-col gap-2">
        <h1 className="font-serif text-3xl font-bold tracking-tight text-gold">
          Position Duels
        </h1>
        <p className="text-sm leading-relaxed text-fg-muted">
          Pick a position, create a challenge on Lichess, and hand each player
          their color link. The game lives on Lichess — no account needed to play.
        </p>
      </section>

      {/* Position picker */}
      <section className="flex flex-col gap-4 rounded-[14px] border border-border bg-surface p-5">
        {/* Source tabs */}
        <div className="flex gap-1 rounded-lg border border-border bg-surface-2 p-1">
          <button
            type="button"
            onClick={handlePasteTab}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              source === "paste"
                ? "bg-gold text-bg shadow-sm"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            Paste FEN
          </button>
          <button
            type="button"
            onClick={() => {
              setSource("curated-mate");
              setResult(null);
              setError(null);
            }}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              source.startsWith("curated")
                ? "bg-gold text-bg shadow-sm"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            Curated
          </button>
        </div>

        {/* Paste FEN tab */}
        {source === "paste" && (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-mono uppercase tracking-wider text-fg-muted">
                FEN
              </span>
              <input
                type="text"
                value={fen}
                onChange={(e) => handleFenChange(e.target.value)}
                placeholder="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-fg placeholder:text-fg-muted/40 focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold/40"
              />
            </label>
            {fenError && (
              <p className="text-xs text-coral">{fenError}</p>
            )}
            {/* Live board preview */}
            {fen.trim() && !fenError && (
              <div className="mt-2">
                <Board
                  fen={fen.trim()}
                  viewOnly
                  ariaLabel="Position preview"
                />
              </div>
            )}
          </div>
        )}

        {/* Curated picker */}
        {source.startsWith("curated") && (
          <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto">
            {CURATED_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => handlePickCurated(opt)}
                className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  fen === opt.fen
                    ? "border-gold bg-gold/10 text-gold"
                    : "border-border bg-surface-2 text-fg hover:border-gold/50"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* Mode toggle */}
        <div className="flex items-center gap-3 pt-2">
          <label className="flex items-center gap-2 text-sm text-fg">
            <input
              type="radio"
              name="duelMode"
              value="realtime"
              checked={mode === "realtime"}
              onChange={() => setMode("realtime")}
              className="accent-gold"
            />
            Realtime (10 min)
          </label>
          <label className="flex items-center gap-2 text-sm text-fg">
            <input
              type="radio"
              name="duelMode"
              value="correspondence"
              checked={mode === "correspondence"}
              onChange={() => setMode("correspondence")}
              className="accent-gold"
            />
            Correspondence (1 day)
          </label>
        </div>

        {/* Create button */}
        <button
          type="button"
          onClick={handleCreate}
          disabled={loading || !!fenError || (!fen.trim() && source === "paste")}
          className="rounded-lg bg-gold px-4 py-2.5 text-sm font-semibold text-bg transition-all hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Creating..." : "Create duel on Lichess"}
        </button>

        {error && (
          <p className="text-sm text-coral">{error}</p>
        )}
      </section>

      {/* Result */}
      {result && (
        <section className="flex flex-col gap-4 rounded-[14px] border border-border bg-surface p-5">
          <h2 className="font-serif text-lg font-semibold text-gold">
            Duel created!
          </h2>

          <p className="text-sm text-fg-muted">
            Send each player their color link. They don't need a Lichess account
            to play — just open the link.
          </p>

          {/* White link */}
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-mono uppercase tracking-wider text-fg-muted">
              White
            </span>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={result.urlWhite}
                className="flex-1 rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-fg"
              />
              <button
                type="button"
                onClick={() => copyToClipboard(result.urlWhite, "white")}
                className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm font-medium text-gold transition-colors hover:border-gold"
              >
                {copied === "white" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Black link */}
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-mono uppercase tracking-wider text-fg-muted">
              Black
            </span>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={result.urlBlack}
                className="flex-1 rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-fg"
              />
              <button
                type="button"
                onClick={() => copyToClipboard(result.urlBlack, "black")}
                className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm font-medium text-gold transition-colors hover:border-gold"
              >
                {copied === "black" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Swap & replay */}
          <button
            type="button"
            onClick={handleSwapAndReplay}
            className="rounded-lg border border-gold/30 bg-gold/5 px-4 py-2 text-sm font-medium text-gold transition-colors hover:bg-gold/10"
          >
            Create another from this position
          </button>
        </section>
      )}
    </main>
  );
}
