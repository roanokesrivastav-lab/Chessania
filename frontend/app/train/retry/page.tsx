"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
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

// ── Types ────────────────────────────────────────────────────────────

interface GradeResult {
  grade: Grade;
  bestLineUci: string;
  bestLineSan: string;
  submittedSan: string;
}

// ── Result config ────────────────────────────────────────────────────

const GRADE_CONFIG: Record<Grade, { label: string; color: string; bg: string }> = {
  perfect: { label: "Perfect", color: "var(--gold)", bg: "var(--gold-bg)" },
  pass: { label: "Pass", color: "var(--green)", bg: "var(--green-bg)" },
  fail: { label: "Fail", color: "var(--coral)", bg: "var(--coral-bg)" },
};

// ── Main trainer ─────────────────────────────────────────────────────

function RetryTrainer() {
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
  // Lazy-loaded; typed loosely since the import is dynamic.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const engineRef = useRef<any>(null);

  // Auth check.
  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  // Load streak.
  useEffect(() => {
    if (user) fetchStreak("retry").then(setStreak);
  }, [user]);

  // Load positions.
  useEffect(() => {
    if (!platform || !username) return;
    fetchRetryPositions(platform, username).then((data) => {
      setPositions(data);
      setLoading(false);
    });
  }, [platform, username]);

  // Cleanup engine on unmount.
  useEffect(() => {
    return () => {
      engineRef.current?.close();
    };
  }, []);

  const currentPosition = positions[currentIndex];

  // Handle a submitted move.
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
          bestLineSan: uciToSan(currentPosition.fen, currentPosition.best_line_uci),
          submittedSan: move.san,
        };
        setFeedback(result);
        setTally((t) => ({ ...t, perfect: t.perfect + 1 }));

        if (user) {
          submitAttempt({
            refId: currentPosition.id,
            trainer: "retry",
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
        // Lazy-init the engine.
        if (!engineRef.current) {
          const { StockfishWasmEngine } = await import("@/lib/engine");
          engineRef.current = new StockfishWasmEngine();
        }

        // Compute the FEN after the submitted move.
        const newFen = computeNewFen(currentPosition.fen, submittedUci);

        // Evaluate the position AFTER the submitted move.
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
          bestLineSan: uciToSan(currentPosition.fen, currentPosition.best_line_uci),
          submittedSan: move.san,
        });
        setTally((t) => ({ ...t, [result]: t[result] + 1 }));

        if (user) {
          submitAttempt({
            refId: currentPosition.id,
            trainer: "retry",
            grade: result,
            seconds,
          }).then((s) => {
            if (s) setStreak(s);
          });
        }
      } catch (err) {
        console.error("Engine grading failed:", err);
        // Fallback: mark as fail on engine error.
        setFeedback({
          grade: "fail",
          bestLineUci: currentPosition.best_line_uci,
          bestLineSan: uciToSan(currentPosition.fen, currentPosition.best_line_uci),
          submittedSan: move.san,
        });
        setTally((t) => ({ ...t, fail: t.fail + 1 }));
      } finally {
        setGrading(false);
      }
    },
    [currentPosition, grading, user]
  );

  // Next position.
  const handleNext = () => {
    setFeedback(null);
    startTimeRef.current = Date.now();
    setCurrentIndex((i) => Math.min(i + 1, positions.length - 1));
  };

  // ── Render states ──────────────────────────────────────────────────

  if (!platform || !username) return <RetryForm />;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
        <p style={{ fontFamily: "var(--font-sans)", color: "var(--text-mid)" }}>Loading positions…</p>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
        <div className="max-w-md text-center" style={{ padding: "2rem", borderRadius: "14px", border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="mb-2" style={{ fontFamily: "var(--font-serif)", fontSize: "1.25rem", fontWeight: 700 }}>No training positions yet</h2>
          <p className="mb-4" style={{ fontFamily: "var(--font-sans)", fontSize: "0.9rem", color: "var(--text-mid)" }}>
            Run a v1 analysis first to mine positions from your games.
          </p>
          <a href="/" style={{ display: "inline-block", padding: "0.6rem 1.5rem", borderRadius: "8px", backgroundColor: "var(--gold)", color: "var(--bg)", fontFamily: "var(--font-mono)", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600, textDecoration: "none" }}>
            Analyze your games
          </a>
        </div>
      </div>
    );
  }

  if (currentIndex >= positions.length) {
    return <SessionComplete tally={tally} streak={streak} onRestart={() => { setCurrentIndex(0); setTally({ perfect: 0, pass: 0, fail: 0 }); setFeedback(null); }} />;
  }

  const playerColor = playerColorFromFen(currentPosition.fen);

  return (
    <div className="flex min-h-screen flex-col items-center p-4" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
      {/* Top bar */}
      <div className="w-full max-w-[560px] mb-3 flex items-center justify-between" style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "var(--text-dim)" }}>
        <span>{currentIndex + 1} / {positions.length}</span>
        <span className="flex gap-3">
          <span style={{ color: "var(--gold)" }}>{tally.perfect}P</span>
          <span style={{ color: "var(--green)" }}>{tally.pass}P</span>
          <span style={{ color: "var(--coral)" }}>{tally.fail}F</span>
        </span>
        {streak.current > 0 && <span>🔥{streak.current}</span>}
      </div>

      {/* Board */}
      <Board fen={currentPosition.fen} orientation={playerColor} interactable onMove={handleMove} ariaLabel={`Retry position ${currentIndex + 1} of ${positions.length} as ${playerColor}`} />

      {/* Grading indicator */}
      {grading && (
        <div className="w-full max-w-[560px] mt-2 text-center" style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "var(--text-dim)" }}>
          Evaluating…
        </div>
      )}

      {/* Feedback panel */}
      {feedback && (
        <div className="w-full max-w-[560px] mt-3" style={{ padding: "1rem", borderRadius: "10px", border: `1px solid ${GRADE_CONFIG[feedback.grade].color}`, backgroundColor: GRADE_CONFIG[feedback.grade].bg, fontFamily: "var(--font-sans)", fontSize: "0.9rem" }}>
          <div className="flex items-center gap-2 mb-2">
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", color: GRADE_CONFIG[feedback.grade].color, fontWeight: 700 }}>
              {GRADE_CONFIG[feedback.grade].label}
            </span>
            <span style={{ color: "var(--text-mid)" }}>
              You played {feedback.submittedSan}
            </span>
          </div>
          {feedback.grade !== "perfect" && (
            <p style={{ color: "var(--text-dim)", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
              Best: {feedback.bestLineSan} ({feedback.bestLineUci})
            </p>
          )}
          <button onClick={handleNext} style={{ padding: "0.4rem 1rem", borderRadius: "6px", border: "none", backgroundColor: "var(--gold)", color: "var(--bg)", fontFamily: "var(--font-mono)", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600, cursor: "pointer" }}>
            Next →{currentIndex + 1 >= positions.length ? " Finish" : ""}
          </button>
        </div>
      )}

      {/* Source game link */}
      <div className="w-full max-w-[560px] mt-2" style={{ fontFamily: "var(--font-mono)", fontSize: "0.65rem", color: "var(--text-dim)" }}>
        <a href={currentPosition.game_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--text-dim)", textDecoration: "none" }}>
          View game ↗
        </a>
      </div>
    </div>
  );
}

// ── Inline form ─────────────────────────────────────────────────────

function RetryForm() {
  const router = useRouter();
  const [platform, setPlatform] = useState("chesscom");
  const [username, setUsername] = useState("");

  return (
    <div className="flex min-h-screen items-center justify-center p-4" style={{ backgroundColor: "var(--bg)" }}>
      <div className="w-full max-w-[400px]" style={{ padding: "2rem", borderRadius: "14px", border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="mb-1" style={{ fontFamily: "var(--font-serif)", fontSize: "1.25rem", fontWeight: 700, color: "var(--text)" }}>Retry Your Mistakes</h2>
        <p className="mb-4" style={{ fontFamily: "var(--font-sans)", fontSize: "0.85rem", color: "var(--text-mid)" }}>
          Practice positions where you blundered — from your own games.
        </p>
        <form onSubmit={(e) => { e.preventDefault(); if (!username.trim()) return; router.push(`/train/retry?platform=${encodeURIComponent(platform)}&username=${encodeURIComponent(username.trim())}`); }}>
          <label className="block mb-1" style={{ fontFamily: "var(--font-mono)", fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-dim)" }}>Platform</label>
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="w-full mb-3" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)", fontFamily: "var(--font-sans)", fontSize: "0.9rem" }}>
            <option value="chesscom">Chess.com</option>
            <option value="lichess">Lichess</option>
          </select>
          <label className="block mb-1" style={{ fontFamily: "var(--font-mono)", fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-dim)" }}>Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="YourChessUsername" required className="w-full mb-4" style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)", fontFamily: "var(--font-sans)", fontSize: "0.9rem", outline: "none" }} />
          <button type="submit" className="w-full" style={{ padding: "0.6rem", borderRadius: "8px", border: "none", backgroundColor: "var(--gold)", color: "var(--bg)", fontFamily: "var(--font-mono)", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600, cursor: "pointer" }}>
            Start training
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Session complete ────────────────────────────────────────────────

function SessionComplete({ tally, streak, onRestart }: { tally: { perfect: number; pass: number; fail: number }; streak: StreakInfo; onRestart: () => void }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
      <div className="max-w-md w-full text-center" style={{ padding: "2rem", borderRadius: "14px", border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="mb-4" style={{ fontFamily: "var(--font-serif)", fontSize: "1.5rem", fontWeight: 700 }}>Session complete!</h2>
        <div className="flex justify-center gap-6 mb-4">
          <ResultChip label="Perfect" count={tally.perfect} color="var(--gold)" bg="var(--gold-bg)" />
          <ResultChip label="Pass" count={tally.pass} color="var(--green)" bg="var(--green-bg)" />
          <ResultChip label="Fail" count={tally.fail} color="var(--coral)" bg="var(--coral-bg)" />
        </div>
        {streak.current > 0 && (
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-dim)", marginBottom: "1.5rem" }}>
            Streak: {streak.current} day{streak.current !== 1 ? "s" : ""} · Best: {streak.best}
          </p>
        )}
        <button onClick={onRestart} style={{ padding: "0.6rem 1.5rem", borderRadius: "8px", border: "1px solid var(--border)", backgroundColor: "transparent", color: "var(--text)", fontFamily: "var(--font-mono)", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600, cursor: "pointer" }}>
          Try again
        </button>
      </div>
    </div>
  );
}

function ResultChip({ label, count, color, bg }: { label: string; count: number; color: string; bg: string }) {
  return (
    <div className="flex flex-col items-center" style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.1em", color }}>
      <span className="text-2xl font-bold mb-1" style={{ color }}>{count}</span>
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

// ── Page export ──────────────────────────────────────────────────────

export default function RetryPage() {
  return (
    <Suspense fallback={null}>
      <RetryTrainer />
    </Suspense>
  );
}
