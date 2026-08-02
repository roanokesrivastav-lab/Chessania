"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Board from "@/components/board/Board";
import type { BoardMove } from "@/components/board/Board";
import {
  gradeMove,
  playerColorFromFen,
  uciToSan,
  type Grade,
} from "@/lib/engine";
import { getSession } from "@/lib/auth";
import type { SessionUser } from "@/lib/auth";
import {
  fetchRetryPositions,
  submitAttempt,
  fetchStreak,
  type PositionItem,
  type StreakInfo,
} from "@/lib/train";
import type { SquareName } from "chessops/types";

// ── Types ────────────────────────────────────────────────────────────

interface GradeResult {
  grade: Grade;
  bestLineUci: string;
  bestLineSan: string;
  submittedSan: string;
}

export interface TrainerShellProps {
  /** Key used for streaks/attempts (e.g. "retry", "preventer"). */
  trainer: string;
  /** Bank category to fetch (e.g. "blunder", "danger"). */
  category: string;
  /** The route path this trainer lives at (e.g. "/train/retry"). Form redirects here. */
  routePath: string;
  /** Form heading (serif). */
  title: string;
  /** Form sub-copy (sans). */
  description: string;
  /** Empty-state body text (defaults to "Run a v1 analysis…"). */
  emptyStateText?: string;
  /** Softer fail-answer copy for kind wrong-answer UX. Defaults to retry's original. */
  failCopy?: { label: string; hint?: string };
  /** Rendered above the board (e.g. opponent's last move in preventer). */
  renderPrompt?: (position: PositionItem) => ReactNode;
}

// ── Result config ────────────────────────────────────────────────────

const GRADE_CONFIG: Record<
  Grade,
  { label: string; color: string; bg: string }
> = {
  perfect: { label: "Perfect", color: "var(--gold)", bg: "var(--gold-bg)" },
  pass: { label: "Pass", color: "var(--green)", bg: "var(--green-bg)" },
  fail: { label: "Fail", color: "var(--coral)", bg: "var(--coral-bg)" },
};

// ── Main component ────────────────────────────────────────────────────

export default function TrainerShell({
  trainer,
  category,
  routePath,
  title,
  description,
  emptyStateText,
  failCopy,
  renderPrompt,
}: TrainerShellProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const platform = searchParams.get("platform") ?? "";
  const username = searchParams.get("username") ?? "";

  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<GradeResult | null>(null);
  const [tally, setTally] = useState({ perfect: 0, pass: 0, fail: 0 });
  const [user, setUser] = useState<SessionUser | null>(null);
  const [streak, setStreak] = useState<StreakInfo>({ current: 0, best: 0 });
  const [grading, setGrading] = useState(false);
  const startTimeRef = useRef(Date.now());
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const engineRef = useRef<any>(null);

  // Use the provided failCopy or fall back to retry's existing labels.
  const failLabel = failCopy?.label ?? GRADE_CONFIG.fail.label;
  const failHint = failCopy?.hint;

  // ── Auth + streak ────────────────────────────────────────────────

  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  useEffect(() => {
    if (user) fetchStreak(trainer).then(setStreak);
  }, [user, trainer]);

  // ── Load positions ───────────────────────────────────────────────

  useEffect(() => {
    if (!platform || !username) return;
    fetchRetryPositions(platform, username, category).then((data) => {
      setPositions(data);
      setLoading(false);
    });
  }, [platform, username, category]);

  // ── Engine cleanup ───────────────────────────────────────────────

  useEffect(() => {
    return () => {
      engineRef.current?.close();
    };
  }, []);

  const currentPosition = positions[currentIndex];

  // ── Handle a submitted move ──────────────────────────────────────

  const handleMove = useCallback(
    async (move: BoardMove) => {
      if (!currentPosition || grading) return;

      const playerColor = playerColorFromFen(currentPosition.fen);
      const submittedUci = move.from + move.to + (move.promotion ?? "");
      const seconds = Math.round((Date.now() - startTimeRef.current) / 1000);
      startTimeRef.current = Date.now();

      // Perfect: matches the stored best line, no engine call needed.
      if (submittedUci === currentPosition.best_line_uci) {
        const result: GradeResult = {
          grade: "perfect",
          bestLineUci: currentPosition.best_line_uci,
          bestLineSan: uciToSan(
            currentPosition.fen,
            currentPosition.best_line_uci,
          ),
          submittedSan: move.san,
        };
        setFeedback(result);
        setTally((t) => ({ ...t, perfect: t.perfect + 1 }));

        if (user) {
          submitAttempt({
            refId: currentPosition.id,
            trainer,
            grade: "perfect",
            seconds,
          }).then((s) => {
            if (s) setStreak(s);
          });
        }
        return;
      }

      // Non-perfect: need engine evaluation.
      setGrading(true);
      try {
        if (!engineRef.current) {
          const { StockfishWasmEngine } = await import("@/lib/engine");
          engineRef.current = new StockfishWasmEngine();
        }

        const newFen = computeNewFen(currentPosition.fen, submittedUci);
        const evalResult = await engineRef.current.evaluate(newFen);

        const result = gradeMove({
          submittedUci,
          bestLineUci: currentPosition.best_line_uci,
          evalBeforeCp: currentPosition.eval_before_cp,
          playerColor,
          evalAfterCp: evalResult.evalCp,
        });

        setFeedback({
          grade: result,
          bestLineUci: currentPosition.best_line_uci,
          bestLineSan: uciToSan(
            currentPosition.fen,
            currentPosition.best_line_uci,
          ),
          submittedSan: move.san,
        });
        setTally((t) => ({ ...t, [result]: t[result] + 1 }));

        if (user) {
          submitAttempt({
            refId: currentPosition.id,
            trainer,
            grade: result,
            seconds,
          }).then((s) => {
            if (s) setStreak(s);
          });
        }
      } catch (err) {
        console.error("Engine grading failed:", err);
        setFeedback({
          grade: "fail",
          bestLineUci: currentPosition.best_line_uci,
          bestLineSan: uciToSan(
            currentPosition.fen,
            currentPosition.best_line_uci,
          ),
          submittedSan: move.san,
        });
        setTally((t) => ({ ...t, fail: t.fail + 1 }));
      } finally {
        setGrading(false);
      }
    },
    [currentPosition, grading, user, trainer],
  );

  // ── Next position ────────────────────────────────────────────────

  const handleNext = () => {
    setFeedback(null);
    startTimeRef.current = Date.now();
    setCurrentIndex((i) => Math.min(i + 1, positions.length - 1));
  };

  // ── Build fallback fail labels from the shell's own GRADE_CONFIG ─
  const baseFailLabel = failLabel;
  const baseFailColor = GRADE_CONFIG.fail.color;
  const baseFailBg = GRADE_CONFIG.fail.bg;

  // ── Render states ──────────────────────────────────────────────────

  if (!platform || !username)
    return (
      <TrainerForm
        title={title}
        description={description}
        onSubmit={(p, u) =>
          router.push(
            `${routePath}?platform=${encodeURIComponent(p)}&username=${encodeURIComponent(u.trim())}`,
          )
        }
      />
    );

  if (loading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center p-4"
        style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
      >
        <p
          style={{
            fontFamily: "var(--font-sans)",
            color: "var(--text-mid)",
          }}
        >
          Loading positions…
        </p>
      </div>
    );
  }

  if (positions.length === 0) {
    const emptyMsg =
      emptyStateText ??
      "Run a v1 analysis first to mine positions from your games.";
    return (
      <div
        className="flex min-h-screen flex-col items-center justify-center p-4"
        style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
      >
        <div
          className="max-w-md text-center"
          style={{
            padding: "2rem",
            borderRadius: "14px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--surface)",
          }}
        >
          <h2
            className="mb-2"
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.25rem",
              fontWeight: 700,
            }}
          >
            No training positions yet
          </h2>
          <p
            className="mb-4"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.9rem",
              color: "var(--text-mid)",
            }}
          >
            {emptyMsg}
          </p>
          <a
            href="/"
            style={{
              display: "inline-block",
              padding: "0.6rem 1.5rem",
              borderRadius: "8px",
              backgroundColor: "var(--gold)",
              color: "var(--bg)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Analyze your games
          </a>
        </div>
      </div>
    );
  }

  if (currentIndex >= positions.length) {
    return (
      <SessionComplete
        tally={tally}
        streak={streak}
        failLabel={baseFailLabel}
        failColor={baseFailColor}
        failBg={baseFailBg}
        onRestart={() => {
          setCurrentIndex(0);
          setTally({ perfect: 0, pass: 0, fail: 0 });
          setFeedback(null);
        }}
      />
    );
  }

  const playerColor = playerColorFromFen(currentPosition.fen);
  const promptContent = renderPrompt?.(currentPosition);

  return (
    <div
      className="flex min-h-screen flex-col items-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      {/* Top bar */}
      <div
        className="w-full max-w-[560px] mb-3 flex items-center justify-between"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.7rem",
          color: "var(--text-dim)",
        }}
      >
        <span>
          {currentIndex + 1} / {positions.length}
        </span>
        <span className="flex gap-3">
          <span style={{ color: "var(--gold)" }}>{tally.perfect}P</span>
          <span style={{ color: "var(--green)" }}>{tally.pass}P</span>
          <span style={{ color: "var(--coral)" }}>{tally.fail}F</span>
        </span>
        {streak.current > 0 && <span>🔥{streak.current}</span>}
      </div>

      {/* Prompt (optional — used by preventer for opponent's move) */}
      {promptContent && (
        <div
          className="w-full max-w-[560px] mb-2"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.85rem",
            color: "var(--text-mid)",
            padding: "0.5rem 0.75rem",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--surface-2)",
          }}
        >
          {promptContent}
        </div>
      )}

      {/* Board */}
      <Board
        fen={currentPosition.fen}
        orientation={playerColor}
        interactable
        onMove={handleMove}
        lastMove={lastMoveFromUci(currentPosition.opponent_move_uci)}
        ariaLabel={`${title} position ${currentIndex + 1} of ${positions.length} as ${playerColor}`}
      />

      {/* Grading indicator */}
      {grading && (
        <div
          className="w-full max-w-[560px] mt-2 text-center"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.7rem",
            color: "var(--text-dim)",
          }}
        >
          Evaluating…
        </div>
      )}

      {/* Feedback panel */}
      {feedback && (
        <div
          className="w-full max-w-[560px] mt-3"
          style={{
            padding: "1rem",
            borderRadius: "10px",
            border: `1px solid ${feedback.grade === "fail" ? baseFailColor : GRADE_CONFIG[feedback.grade].color}`,
            backgroundColor:
              feedback.grade === "fail"
                ? baseFailBg
                : GRADE_CONFIG[feedback.grade].bg,
            fontFamily: "var(--font-sans)",
            fontSize: "0.9rem",
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color:
                  feedback.grade === "fail"
                    ? baseFailColor
                    : GRADE_CONFIG[feedback.grade].color,
                fontWeight: 700,
              }}
            >
              {feedback.grade === "fail"
                ? baseFailLabel
                : GRADE_CONFIG[feedback.grade].label}
            </span>
            <span style={{ color: "var(--text-mid)" }}>
              You played {feedback.submittedSan}
            </span>
          </div>
          {feedback.grade !== "perfect" && (
            <>
              <p
                style={{
                  color: "var(--text-dim)",
                  fontSize: "0.8rem",
                  marginBottom: failHint ? "0.25rem" : "0.5rem",
                }}
              >
                Best: {feedback.bestLineSan} ({feedback.bestLineUci})
              </p>
              {feedback.grade === "fail" && failHint && (
                <p
                  style={{
                    color: baseFailColor,
                    fontSize: "0.8rem",
                    marginBottom: "0.5rem",
                    fontFamily: "var(--font-serif)",
                  }}
                >
                  {failHint}
                </p>
              )}
            </>
          )}
          <button
            onClick={handleNext}
            style={{
              padding: "0.4rem 1rem",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "var(--gold)",
              color: "var(--bg)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Next →{currentIndex + 1 >= positions.length ? " Finish" : ""}
          </button>
        </div>
      )}

      {/* Source game link */}
      <div
        className="w-full max-w-[560px] mt-2"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.65rem",
          color: "var(--text-dim)",
        }}
      >
        <a
          href={currentPosition.game_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--text-dim)", textDecoration: "none" }}
        >
          View game ↗
        </a>
      </div>
    </div>
  );
}

// ── Inline form ─────────────────────────────────────────────────────

function TrainerForm({
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
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)" }}
    >
      <div
        className="w-full max-w-[400px]"
        style={{
          padding: "2rem",
          borderRadius: "14px",
          border: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <h2
          className="mb-1"
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.25rem",
            fontWeight: 700,
            color: "var(--text)",
          }}
        >
          {title}
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.85rem",
            color: "var(--text-mid)",
          }}
        >
          {description}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!username.trim()) return;
            onSubmit(platform, username);
          }}
        >
          <label
            className="block mb-1"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.65rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--text-dim)",
            }}
          >
            Platform
          </label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="w-full mb-3"
            style={{
              padding: "0.6rem 0.8rem",
              borderRadius: "8px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg)",
              color: "var(--text)",
              fontFamily: "var(--font-sans)",
              fontSize: "0.9rem",
            }}
          >
            <option value="chesscom">Chess.com</option>
            <option value="lichess">Lichess</option>
          </select>
          <label
            className="block mb-1"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.65rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--text-dim)",
            }}
          >
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="YourChessUsername"
            required
            className="w-full mb-4"
            style={{
              padding: "0.6rem 0.8rem",
              borderRadius: "8px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg)",
              color: "var(--text)",
              fontFamily: "var(--font-sans)",
              fontSize: "0.9rem",
              outline: "none",
            }}
          />
          <button
            type="submit"
            className="w-full"
            style={{
              padding: "0.6rem",
              borderRadius: "8px",
              border: "none",
              backgroundColor: "var(--gold)",
              color: "var(--bg)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Start training
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Session complete ────────────────────────────────────────────────

function SessionComplete({
  tally,
  streak,
  failLabel,
  failColor,
  failBg,
  onRestart,
}: {
  tally: { perfect: number; pass: number; fail: number };
  streak: StreakInfo;
  failLabel: string;
  failColor: string;
  failBg: string;
  onRestart: () => void;
}) {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      <div
        className="max-w-md w-full text-center"
        style={{
          padding: "2rem",
          borderRadius: "14px",
          border: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <h2
          className="mb-4"
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.5rem",
            fontWeight: 700,
          }}
        >
          Session complete!
        </h2>
        <div className="flex justify-center gap-6 mb-4">
          <ResultChip
            label="Perfect"
            count={tally.perfect}
            color="var(--gold)"
            bg="var(--gold-bg)"
          />
          <ResultChip
            label="Pass"
            count={tally.pass}
            color="var(--green)"
            bg="var(--green-bg)"
          />
          <ResultChip
            label={failLabel}
            count={tally.fail}
            color={failColor}
            bg={failBg}
          />
        </div>
        {streak.current > 0 && (
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "var(--text-dim)",
              marginBottom: "1.5rem",
            }}
          >
            Streak: {streak.current} day{streak.current !== 1 ? "s" : ""} · Best:{" "}
            {streak.best}
          </p>
        )}
        <button
          onClick={onRestart}
          style={{
            padding: "0.6rem 1.5rem",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            backgroundColor: "transparent",
            color: "var(--text)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}

function ResultChip({
  label,
  count,
  color,
  bg,
}: {
  label: string;
  count: number;
  color: string;
  bg: string;
}) {
  return (
    <div
      className="flex flex-col items-center"
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: "0.7rem",
        textTransform: "uppercase",
        letterSpacing: "0.1em",
        color,
      }}
    >
      <span className="text-2xl font-bold mb-1" style={{ color }}>
        {count}
      </span>
      <span>{label}</span>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

/**
 * Compute the FEN after making a UCI move from a given FEN.
 * Uses chessops for correctness.
 */
function computeNewFen(fen: string, uci: string): string {
  try {
    const { Chess } = require("chessops/chess");
    const { parseFen, makeFen } = require("chessops/fen");
    const { parseUci } = require("chessops");

    const setup = parseFen(fen).unwrap();
    const pos = Chess.fromSetup(setup).unwrap();
    const move = parseUci(uci);
    if (!move) return fen;
    pos.play(move);
    return makeFen(pos.toSetup());
  } catch {
    return fen;
  }
}

/**
 * Convert a UCI string like "e7e5" into a chessground lastMove tuple
 * like ["e7", "e5"]. Returns null for malformed or missing UCI.
 */
function lastMoveFromUci(uci: string | null): [SquareName, SquareName] | null {
  if (!uci || uci.length < 4) return null;
  return [uci.substring(0, 2) as SquareName, uci.substring(2, 4) as SquareName];
}
