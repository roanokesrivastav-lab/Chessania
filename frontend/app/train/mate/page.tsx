"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Board from "@/components/board/Board";
import type { BoardMove } from "@/components/board/Board";
import { Chess } from "chessops/chess";
import { parseFen, makeFen } from "chessops/fen";
import { parseUci } from "chessops";
import { chessgroundDests } from "chessops/compat";
import { StockfishWasmEngine } from "@/lib/engine";
import { getSession } from "@/lib/auth";
import type { SessionUser } from "@/lib/auth";
import { submitAttempt, fetchStreak, type StreakInfo } from "@/lib/train";
import { MATE_SET, type MatePosition } from "@/lib/mateSet";

// ── Helpers ──────────────────────────────────────────────────────────

function applyMove(pos: Chess, uci: string): string | null {
  try {
    const move = parseUci(uci);
    if (!move) return null;
    if (!pos.isLegal(move)) return null;
    pos.play(move);
    return makeFen(pos.toSetup());
  } catch {
    return null;
  }
}

// ── Sub-components ────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      <p style={{ fontFamily: "var(--font-sans)", color: "var(--text-mid)" }}>
        Loading…
      </p>
    </div>
  );
}

function IntroPanel({ totalPositions, onStart }: { totalPositions: number; onStart: () => void }) {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      <div
        className="w-full max-w-[480px] text-center"
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
            fontSize: "1.5rem",
            fontWeight: 700,
          }}
        >
          Checkmate Challenges
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.9rem",
            color: "var(--text-mid)",
            lineHeight: 1.6,
          }}
        >
          {totalPositions} curated checkmate puzzles — from basic mates to
          common patterns. Find the forcing line against the engine&rsquo;s best
          defense.
        </p>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-dim)",
          }}
        >
          Delivering mate = pass. Delivering it in the optimal number of moves =
          perfect. If the king escapes, try again.
        </p>
        <button
          onClick={onStart}
          style={{
            padding: "0.7rem 2rem",
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
          Start — {totalPositions} challenge{totalPositions !== 1 ? "s" : ""}
        </button>
      </div>
    </div>
  );
}

function SessionCompletePanel({
  tally,
  onNewSession,
}: {
  tally: { perfect: number; pass: number };
  onNewSession: () => void;
}) {
  const total = tally.perfect + tally.pass;
  const pct = total > 0 ? Math.round((tally.perfect / total) * 100) : 0;

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      <div
        className="w-full max-w-[420px] text-center"
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
          Session Complete
        </h2>
        <div className="mb-3 flex justify-center gap-4">
          <div>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "1.5rem",
                color: "var(--gold)",
                fontWeight: 700,
              }}
            >
              {tally.perfect}
            </span>
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "0.75rem",
                color: "var(--text-dim)",
                display: "block",
              }}
            >
              perfect
            </span>
          </div>
          <div>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "1.5rem",
                color: "var(--green)",
                fontWeight: 700,
              }}
            >
              {tally.pass}
            </span>
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "0.75rem",
                color: "var(--text-dim)",
                display: "block",
              }}
            >
              pass
            </span>
          </div>
        </div>
        {total > 0 && (
          <p
            className="mb-3"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.85rem",
              color: "var(--text-mid)",
            }}
          >
            {pct}% optimal — {tally.perfect} of {total}
          </p>
        )}
        <button
          onClick={onNewSession}
          style={{
            padding: "0.7rem 2rem",
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
          Start new session
        </button>
      </div>
    </div>
  );
}

// ── Main trainer component ──────────────────────────────────────────

function MatePageInner() {
  // ── Flow state ──────────────────────────────────────────────────
  const [phase, setPhase] = useState<"intro" | "playing" | "sessionComplete">("intro");
  const [posIndex, setPosIndex] = useState(0);

  // ── Game state ──────────────────────────────────────────────────
  const [currentFen, setCurrentFen] = useState("");
  const [engineThinking, setEngineThinking] = useState(false);
  const [gameResult, setGameResult] = useState<"win" | "lostMate" | null>(null);
  const [userMoveCount, setUserMoveCount] = useState(0);
  const [hintShown, setHintShown] = useState(false);

  // ── Session tally ───────────────────────────────────────────────
  const [tally, setTally] = useState({ perfect: 0, pass: 0 });
  const [user, setUser] = useState<SessionUser | null>(null);
  const [streak, setStreak] = useState<StreakInfo>({ current: 0, best: 0 });

  // ── Refs ────────────────────────────────────────────────────────
  const engineRef = useRef<StockfishWasmEngine | null>(null);
  const posRef = useRef<Chess | null>(null);
  const startTimeRef = useRef(Date.now());
  const attemptSubmitted = useRef(false);
  const currentPositionRef = useRef<MatePosition | null>(null);

  const currentPosition = MATE_SET[posIndex];
  const isUserTurn = gameResult === null && !engineThinking;

  // ── Auth + streak ───────────────────────────────────────────────
  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  useEffect(() => {
    if (user) fetchStreak("mate").then(setStreak);
  }, [user]);

  // ── Engine cleanup ──────────────────────────────────────────────
  useEffect(() => {
    return () => {
      engineRef.current?.close();
    };
  }, []);

  // ── Initialize a position ───────────────────────────────────────
  const initPosition = useCallback(async (position: MatePosition) => {
    engineRef.current?.close();
    currentPositionRef.current = position;
    attemptSubmitted.current = false;
    setHintShown(false);
    setUserMoveCount(0);

    const setup = parseFen(position.fen);
    if (setup.isErr) return;
    const pos = Chess.fromSetup(setup.unwrap());
    if (pos.isErr) return;
    posRef.current = pos.unwrap();
    setCurrentFen(position.fen);
    setGameResult(null);
    setEngineThinking(false); // unlock the board for the new/retried position
    startTimeRef.current = Date.now();

    const engine = new StockfishWasmEngine();
    engineRef.current = engine;
  }, []);

  // ── Initialize when posIndex or phase changes ───────────────────
  useEffect(() => {
    const pos = MATE_SET[posIndex];
    if (!pos || phase !== "playing") return;
    initPosition(pos);
  }, [posIndex, phase, initPosition]);

  // ── Engine defense ──────────────────────────────────────────────
  const doEngineMove = useCallback(async () => {
    const engine = engineRef.current;
    const pos = posRef.current;
    if (!engine || !pos) return;

    setEngineThinking(true);
    try {
      const fen = makeFen(pos.toSetup());
      const result = await engine.evaluate(fen);
      const newFen = applyMove(pos, result.bestMoveUci);
      if (!newFen) {
        // Engine gave illegal move — treat as user win.
        setGameResult("win");
        setEngineThinking(false);
        return;
      }
      setCurrentFen(newFen);

      // If the user is in checkmate after engine's move, lost the forced mate.
      if (pos.isCheckmate()) {
        setGameResult("lostMate");
      }
    } catch (err) {
      console.error("Engine move failed:", err);
    } finally {
      setEngineThinking(false);
    }
  }, []);

  // ── Handle user move ────────────────────────────────────────────
  const handleUserMove = useCallback(
    (move: BoardMove) => {
      if (gameResult !== null || engineThinking) return;

      const pos = posRef.current;

      // Lock the board immediately to prevent double-moves during async evaluate.
      setEngineThinking(true);
      const position = currentPositionRef.current;
      if (!pos || !position) return;

      const uci = move.from + move.to + (move.promotion ?? "");
      const newFen = applyMove(pos, uci);
      if (!newFen) return;

      setCurrentFen(newFen);
      const newMoveCount = userMoveCount + 1;
      setUserMoveCount(newMoveCount);

      // Check if user delivered checkmate.
      if (pos.isCheckmate()) {
        setEngineThinking(false);
        setGameResult("win");
        return;
      }

      // Not yet mate — evaluate the resulting position.
      // The engine (opponent) is now to move. If mateIn < 0, the opponent
      // is getting mated → mate is still on. Otherwise, lost it.
      const engine = engineRef.current;
      if (engine) {
        engine.evaluate(newFen).then((result) => {
          // mateIn is side-to-move POV. After user's move, opponent is to move.
          // mateIn < 0 means opponent (side-to-move) gets mated → still on.
          if (result.mateIn != null && result.mateIn < 0) {
            // Mate intact — let the engine defend (doEngineMove owns the lock).
            setTimeout(() => doEngineMove(), 300);
          } else {
            // Mate lost — user didn't maintain the forced mate.
            setEngineThinking(false);
            setGameResult("lostMate");
          }
        }).catch(() => {
          setEngineThinking(false);
          setGameResult("lostMate");
        });
      }
    },
    [gameResult, engineThinking, userMoveCount, doEngineMove],
  );

  // ── Submit attempt when game ends ───────────────────────────────
  useEffect(() => {
    if (!gameResult || !currentPositionRef.current || attemptSubmitted.current) return;
    attemptSubmitted.current = true;

    // Only submit when user delivered mate (win).
    if (gameResult !== "win") return;

    // Grade: perfect if userMateCount == mateInN, else pass.
    const pos = currentPositionRef.current;
    const grade = userMoveCount === pos.mateInN ? "perfect" : "pass";
    const seconds = Math.round((Date.now() - startTimeRef.current) / 1000);

    // Update tally.
    setTally((t) => {
      if (grade === "perfect") return { ...t, perfect: t.perfect + 1 };
      return { ...t, pass: t.pass + 1 };
    });

    if (user) {
      submitAttempt({
        refId: pos.id,
        refType: "curated",
        trainer: "mate",
        grade,
        seconds,
      }).then((s) => {
        if (s) setStreak(s);
      });
    }
  }, [gameResult, userMoveCount, user]);

  // ── Retry (after lostMate) ──────────────────────────────────────
  const handleRetry = useCallback(() => {
    setHintShown(false);
    const pos = MATE_SET[posIndex];
    if (pos) initPosition(pos);
  }, [posIndex, initPosition]);

  // ── Show hint ───────────────────────────────────────────────────
  const handleShowHint = useCallback(() => {
    setHintShown(true);
  }, []);

  // ── Next position ───────────────────────────────────────────────
  const handleNext = useCallback(() => {
    const nextIndex = posIndex + 1;
    if (nextIndex >= MATE_SET.length) {
      engineRef.current?.close();
      setPhase("sessionComplete");
      return;
    }
    setPosIndex(nextIndex);
  }, [posIndex]);

  // ── Start ───────────────────────────────────────────────────────
  const handleStart = useCallback(() => {
    setPhase("playing");
    setPosIndex(0);
    setTally({ perfect: 0, pass: 0 });
  }, []);

  // ── New session ─────────────────────────────────────────────────
  const handleNewSession = useCallback(() => {
    setTally({ perfect: 0, pass: 0 });
    setPosIndex(0);
    setPhase("intro");
  }, []);

  // ── Orientation ─────────────────────────────────────────────────
  const orientation = currentPosition?.playerColor ?? "white";

  // ── Render ──────────────────────────────────────────────────────
  if (phase === "intro") {
    return <IntroPanel totalPositions={MATE_SET.length} onStart={handleStart} />;
  }

  if (phase === "sessionComplete") {
    return <SessionCompletePanel tally={tally} onNewSession={handleNewSession} />;
  }

  if (!currentPosition) {
    return <LoadingState />;
  }

  return (
    <div
      className="flex min-h-screen flex-col items-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <div
        className="mb-3 flex w-full max-w-[560px] items-center justify-between"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.65rem",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "var(--text-dim)",
        }}
      >
        <span>
          {posIndex + 1} / {MATE_SET.length}
        </span>
        <span>
          {currentPosition.pattern} — mate in {currentPosition.mateInN}
        </span>
        <span>
          <span style={{ color: "var(--gold)" }}>{tally.perfect}p</span>{" "}
          <span style={{ color: "var(--green)" }}>{tally.pass}p</span>
        </span>
      </div>

      {/* ── Streak (signed-in only) ─────────────────────────────── */}
      {user && streak.current > 0 && (
        <div
          className="mb-2 text-center"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.6rem",
            color: "var(--text-dim)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          mate streak: {streak.current} day{streak.current !== 1 ? "s" : ""}{" "}
          (best: {streak.best})
        </div>
      )}

      {/* ── Board ───────────────────────────────────────────────── */}
      <Board
        fen={currentFen || currentPosition.fen}
        orientation={orientation}
        interactable={isUserTurn}
        onMove={handleUserMove}
        ariaLabel="Mate challenge board"
      />

      {/* ── Engine thinking indicator ───────────────────────────── */}
      {engineThinking && (
        <div
          className="mt-2"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.65rem",
            color: "var(--text-dim)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          Engine thinking…
        </div>
      )}

      {/* ── Result panel ────────────────────────────────────────── */}
      {gameResult === "win" && (
        <div
          className="mt-3 w-full max-w-[560px]"
          style={{
            padding: "1rem",
            borderRadius: "10px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--surface)",
          }}
        >
          <div className="flex items-center gap-3">
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color:
                  userMoveCount === currentPosition.mateInN
                    ? "var(--gold)"
                    : "var(--green)",
              }}
            >
              {userMoveCount === currentPosition.mateInN ? "★ Perfect" : "✓ Pass"}
            </span>
            <span
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "0.8rem",
                color: "var(--text-mid)",
              }}
            >
              Mate delivered in {userMoveCount} move
              {userMoveCount !== 1 ? "s" : ""}
              {userMoveCount !== currentPosition.mateInN && (
                <> (optimal: {currentPosition.mateInN})</>
              )}
            </span>
          </div>
          <button
            onClick={handleNext}
            className="mt-2"
            style={{
              padding: "0.5rem 1.5rem",
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
            {posIndex + 1 < MATE_SET.length ? "Next" : "Finish"}
          </button>
        </div>
      )}

      {/* ── Lost-mate panel ─────────────────────────────────────── */}
      {gameResult === "lostMate" && (
        <div
          className="mt-3 w-full max-w-[560px]"
          style={{
            padding: "1rem",
            borderRadius: "10px",
            border: "1px solid var(--coral)",
            backgroundColor: "var(--surface)",
          }}
        >
          <p
            className="mb-2"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.85rem",
              color: "var(--coral)",
              fontWeight: 600,
            }}
          >
            That lets the king escape — try again.
          </p>
          <p
            className="mb-2"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.8rem",
              color: "var(--text-mid)",
            }}
          >
            You had a forced mate in {currentPosition.mateInN} but lost the
            thread. Look at the position again and find the forcing line.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleRetry}
              style={{
                padding: "0.5rem 1.5rem",
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
              Retry
            </button>
            {!hintShown && (
              <button
                onClick={handleShowHint}
                style={{
                  padding: "0.5rem 1.5rem",
                  borderRadius: "6px",
                  border: "1px solid var(--border)",
                  backgroundColor: "transparent",
                  color: "var(--text-mid)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.7rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  cursor: "pointer",
                }}
              >
                Show first move
              </button>
            )}
          </div>
          {hintShown && (
            <p
              className="mt-2"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.8rem",
                color: "var(--gold)",
                fontWeight: 600,
              }}
            >
              First move: {currentPosition.firstMoveSan}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page export (wrapped in Suspense for useSearchParams) ───────────

export default function MatePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <MatePageInner />
    </Suspense>
  );
}
