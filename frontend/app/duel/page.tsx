"use client";
// V2-S10 + V2-S11: Position Duels — library (browse positions) + create
// flow (Lichess challenge from a FEN, share-links, history).

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { parseFen } from "chessops/fen";

import Board from "@/components/board/Board";
import {
  createDuel,
  listMyDuels,
  type DuelResponse,
  type DuelHistoryItem,
} from "@/lib/duels";
import { ENDGAME_SET } from "@/lib/endgameSet";
import { fetchRetryPositions, type PositionItem } from "@/lib/train";
import { getSession } from "@/lib/auth";
import type { SessionUser } from "@/lib/auth";

// ── Types ────────────────────────────────────────────────────────────

type DuelMode = "realtime" | "correspondence";
type PositionSource = "paste" | "curated-mate" | "curated-endgame";

// ── Constants ────────────────────────────────────────────────────────

const LIBRARY_ENDGAMES = ENDGAME_SET.map((e) => ({
  id: e.id,
  fen: e.fen,
  label: `${e.pattern} (${e.target === "win" ? "Win" : "Hold"})`,
  sub: e.why,
  source: "curated-endgame" as const,
}));

// ── Shared inline form (matches TrainerShell pattern) ────────────────

function InlinePlayerForm({
  title,
  description,
  onSubmit,
}: {
  title: string;
  description: string;
  onSubmit: (platform: string, username: string) => void;
}) {
  const [platform, setPlatform] = useState("chesscom");
  const [username, setUsername] = useState("");

  return (
    <div className="flex flex-col gap-3 rounded-[14px] border border-border bg-surface p-4">
      <div>
        <h3 className="font-serif text-base font-semibold text-fg">
          {title}
        </h3>
        <p className="text-xs text-fg-muted">{description}</p>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!username.trim()) return;
          onSubmit(platform, username.trim());
        }}
        className="flex flex-col gap-2"
      >
        <div className="flex gap-2">
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
        </div>
      </form>
    </div>
  );
}

// ── Library row (compact, no live board) ─────────────────────────────

function LibraryRow({
  label,
  sub,
  onSelect,
}: {
  label: string;
  sub?: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex flex-col gap-0.5 rounded-lg border border-border bg-surface-2 px-3 py-2 text-left transition-colors hover:border-gold/50 w-full"
    >
      <span className="text-sm font-medium text-fg">{label}</span>
      {sub && (
        <span className="text-xs text-fg-muted line-clamp-1 overflow-hidden">{sub}</span>
      )}
    </button>
  );
}

// ── Library section ─────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="font-serif text-sm font-semibold uppercase tracking-wide text-fg-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

// ── Copy button ─────────────────────────────────────────────────────

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-xs font-medium text-gold transition-colors hover:border-gold"
    >
      {copied ? "Copied!" : label}
    </button>
  );
}

// ── History row ────────────────────────────────────────────────────

function HistoryRow({ duel }: { duel: DuelHistoryItem }) {
  const date = duel.created_at
    ? new Date(duel.created_at).toLocaleDateString()
    : "";

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface-2 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-fg-muted">{date}</span>
        <span className="text-xs text-fg-muted">
          {duel.source === "paste"
            ? "Custom FEN"
            : duel.source === "curated-endgame"
              ? "Endgame"
              : duel.source}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          readOnly
          value={duel.urlWhite}
          className="flex-1 rounded border border-border bg-bg px-2 py-1 font-mono text-xs text-fg"
        />
        <CopyButton text={duel.urlWhite} label="White" />
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          readOnly
          value={duel.urlBlack}
          className="flex-1 rounded border border-border bg-bg px-2 py-1 font-mono text-xs text-fg"
        />
        <CopyButton text={duel.urlBlack} label="Black" />
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────

export default function DuelPage() {
  // ── Create flow state ──────────────────────────────────────────
  const [fen, setFen] = useState("");
  const [fenError, setFenError] = useState<string | null>(null);
  const [mode, setMode] = useState<DuelMode>("realtime");
  const [source, setSource] = useState<PositionSource>("paste");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DuelResponse | null>(null);

  // ── Bank sections state ───────────────────────────────────────
  const [bankPlatform, setBankPlatform] = useState("");
  const [bankUsername, setBankUsername] = useState("");
  const [unconverted, setUnconverted] = useState<PositionItem[]>([]);
  const [blunders, setBlunders] = useState<PositionItem[]>([]);
  const [bankLoading, setBankLoading] = useState(false);

  // ── History state ─────────────────────────────────────────────
  const [user, setUser] = useState<SessionUser | null>(null);
  const [history, setHistory] = useState<DuelHistoryItem[]>([]);

  // Auth check on mount.
  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  // Load duel history when signed in.
  useEffect(() => {
    if (user) {
      listMyDuels().then(setHistory);
    }
  }, [user]);

  // ── FEN validation ────────────────────────────────────────────
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

  const selectFen = useCallback(
    (newFen: string, newSource: PositionSource) => {
      setFen(newFen);
      setSource(newSource);
      setFenError(null);
      setError(null);
      setResult(null);
    },
    [],
  );

  // ── Load bank positions ───────────────────────────────────────
  const handleLoadBank = (platform: string, username: string) => {
    setBankPlatform(platform);
    setBankUsername(username);
    setBankLoading(true);
    Promise.all([
      fetchRetryPositions(platform, username, "unconverted", 10),
      fetchRetryPositions(platform, username, "blunder", 10),
    ]).then(([unc, bln]) => {
      setUnconverted(unc);
      setBlunders(bln);
      setBankLoading(false);
    });
  };

  // ── Create duel ───────────────────────────────────────────────
  const handleCreate = async () => {
    setError(null);
    setResult(null);

    const trimmed = fen.trim();
    if (!trimmed) {
      setError("Please enter a FEN or pick a position from the library.");
      return;
    }

    const parsed = parseFen(trimmed);
    if (parsed.isErr) {
      setError("That position doesn't look valid — check the FEN and try again.");
      return;
    }

    setLoading(true);
    try {
      const duel = await createDuel({ fen: trimmed, source, mode });
      setResult(duel);
      // Refresh history after creating a duel (if signed in).
      if (user) listMyDuels().then(setHistory);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong — try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSwapAndReplay = () => setResult(null);

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

      {/* ── POSITION PICKER + CREATE ────────────────────────────── */}
      <section className="flex flex-col gap-4 rounded-[14px] border border-border bg-surface p-5">
        {/* Source tabs */}
        <div className="flex gap-1 rounded-lg border border-border bg-surface-2 p-1">
          <button
            type="button"
            onClick={() => {
              setSource("paste");
              setResult(null);
              setError(null);
            }}
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
              setSource("curated-endgame");
              setResult(null);
              setError(null);
            }}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              source.startsWith("curated")
                ? "bg-gold text-bg shadow-sm"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            Library
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
                onChange={(e) => {
                  setFen(e.target.value);
                  validateFen(e.target.value);
                }}
                placeholder="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-fg placeholder:text-fg-muted/40 focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold/40"
              />
            </label>
            {fenError && (
              <p className="text-xs text-coral">{fenError}</p>
            )}
            {fen.trim() && !fenError && (
              <div className="mt-2">
                <Board fen={fen.trim()} viewOnly ariaLabel="Position preview" />
              </div>
            )}
          </div>
        )}

        {/* Library tabs (no mate set — poor duel material) */}
        {source.startsWith("curated") && (
          <p className="text-xs text-fg-muted py-2">
            Browse the <strong>Classic endgames</strong> and <strong>Your analyzed positions</strong> sections below to pick a position, then come back here to create your duel.
          </p>
        )}

        {/* Paste FEN tab continued — preview + mode + create */}

        {/* Preview + mode toggle + create (always visible when a FEN is set) */}
        {fen.trim() && !fenError && source.startsWith("curated") && (
          <div className="mt-2">
            <Board fen={fen.trim()} viewOnly ariaLabel="Position preview" />
          </div>
        )}

        {fen.trim() && !fenError && (
          <>
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

            <button
              type="button"
              onClick={handleCreate}
              disabled={loading || !!fenError}
              className="rounded-lg bg-gold px-4 py-2.5 text-sm font-semibold text-bg transition-all hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Creating..." : "Create duel on Lichess"}
            </button>

            {error && <p className="text-sm text-coral">{error}</p>}
          </>
        )}
      </section>

      {/* ── RESULT ──────────────────────────────────────────────── */}
      {result && (
        <section className="flex flex-col gap-4 rounded-[14px] border border-border bg-surface p-5">
          <h2 className="font-serif text-lg font-semibold text-gold">
            Duel created!
          </h2>

          <p className="text-sm text-fg-muted">
            Send each player their color link. They don&rsquo;t need a Lichess
            account to play — just open the link.
          </p>

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
              <CopyButton text={result.urlWhite} label="Copy" />
            </div>
          </div>

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
              <CopyButton text={result.urlBlack} label="Copy" />
            </div>
          </div>

          <button
            type="button"
            onClick={handleSwapAndReplay}
            className="rounded-lg border border-gold/30 bg-gold/5 px-4 py-2 text-sm font-medium text-gold transition-colors hover:bg-gold/10"
          >
            Create another from this position
          </button>
        </section>
      )}

      {/* ── CLASSIC ENDGAMES LIBRARY ────────────────────────────── */}
      <Section title="Classic endgames">
        <p className="text-xs text-fg-muted">
          Curated endgame positions — perfect duel material. Click one to
          select it above, then create your duel.
        </p>
        <div className="flex flex-col gap-1.5">
          {LIBRARY_ENDGAMES.map((eg) => (
            <LibraryRow
              key={eg.id}
              label={eg.label}
              sub={eg.sub}
              onSelect={() => selectFen(eg.fen, "curated-endgame")}
            />
          ))}
        </div>
      </Section>

      {/* ── YOUR POSITIONS (BANK) ───────────────────────────────── */}
      <Section title="Your analyzed positions">
        {!bankPlatform ? (
          <InlinePlayerForm
            title="Load your positions"
            description="Enter your platform and username to see positions from your own analyzed games."
            onSubmit={handleLoadBank}
          />
        ) : (
          <>
            <p className="text-xs text-fg-muted">
              Positions from{" "}
              <strong>
                {bankUsername} ({bankPlatform})
              </strong>
            </p>

            {bankLoading ? (
              <p className="text-sm text-fg-muted">Loading…</p>
            ) : (
              <>
                {/* Unconverted */}
                <Section title={`Your unconverted positions (${unconverted.length})`}>
                  {unconverted.length === 0 ? (
                    <p className="text-xs text-fg-muted">
                      No unconverted positions yet. Run a v1 analysis first.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {unconverted.slice(0, 5).map((p) => (
                        <LibraryRow
                          key={p.id}
                          label={`Move ${p.ply} · ${p.played_at ? new Date(p.played_at).toLocaleDateString() : "Unknown date"}`}
                          sub={p.game_url}
                          onSelect={() => selectFen(p.fen, "curated-endgame")}
                        />
                      ))}
                    </div>
                  )}
                </Section>

                {/* Blunders */}
                <Section title={`Your recent mistakes (${blunders.length})`}>
                  {blunders.length === 0 ? (
                    <p className="text-xs text-fg-muted">
                      No blunder positions yet. Run a v1 analysis first.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {blunders.slice(0, 5).map((p) => (
                        <LibraryRow
                          key={p.id}
                          label={`Move ${p.ply} · ${p.played_at ? new Date(p.played_at).toLocaleDateString() : "Unknown date"}`}
                          sub={p.game_url}
                          onSelect={() => selectFen(p.fen, "curated-endgame")}
                        />
                      ))}
                    </div>
                  )}
                </Section>

                <button
                  type="button"
                  onClick={() => {
                    setBankPlatform("");
                    setBankUsername("");
                    setUnconverted([]);
                    setBlunders([]);
                  }}
                  className="text-xs text-fg-muted underline hover:text-fg"
                >
                  Change player
                </button>
              </>
            )}
          </>
        )}
      </Section>

      {/* ── DUEL HISTORY ────────────────────────────────────────── */}
      <Section title="Your duels">
        {!user ? (
          <p className="text-xs text-fg-muted">
            <a href="/login" className="text-gold underline hover:text-gold/80">
              Sign in
            </a>{" "}
            to keep your duel history.
          </p>
        ) : history.length === 0 ? (
          <p className="text-xs text-fg-muted">
            No duels yet — create one above and they&rsquo;ll show up here.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {history.map((d) => (
              <HistoryRow key={d.id} duel={d} />
            ))}
          </div>
        )}
      </Section>
    </main>
  );
}
