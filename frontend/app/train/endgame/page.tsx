"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";
import { ENDGAME_SET, type EndgamePosition } from "@/lib/endgameSet";

// ── Constants ────────────────────────────────────────────────────────

/** Engine movetime for opponent moves (ms). Full-strength engine, no Elo cap. */
const ENGINE_MOVETIME_MS = 500;

/** Halfmove clock threshold for the 50-move rule. */
const FIFTY_MOVE_HALFMOVES = 100;

/** Adjudication thresholds (V2-S9 Hard Rules).
 *
 *  DRAW_BAND=150:   target="win"  + playerPovEval <= 150  → threw the win.
 *                   "The opponent has equalized — you let a win slip."
 *
 *  CONVERTED_CP=900: target="win"  + playerPovEval >= 900  → clearly winning.
 *                    "You've built a decisive advantage — well converted."
 *
 *  LOST_HOLD_CP=-300: target="draw" + playerPovEval <= -300 → lost the hold.
 *                     "The position has swung — you lost the draw."
 *
 *  MOVE_CAP=30:      full moves (60 halfmoves). Long enough to show technique
 *                    without infinite dragging. target="draw" → pass (held);
 *                    target="win"  → fail (not converted). */
const DRAW_BAND = 150;
const CONVERTED_CP = 900;
const LOST_HOLD_CP = -300;
const MOVE_CAP = 30;

// ── Types ────────────────────────────────────────────────────────────

type GameResult = "pass" | "fail";

// ── Helpers ──────────────────────────────────────────────────────────

/** Check if the position is terminal (checkmate / stalemate / 50-move rule /
 *  insufficient material).  Returns the adjudicated result or null.
 *
 *  The returned value is from the PLAYER's perspective:
 *  - "pass" = player won (checkmated engine) or drew when target="draw"
 *  - "fail" = player lost (was checkmated) or drew when target="win"
 *  - null   = game still in progress.
 *
 *  Threefold repetition is explicitly OUT of scope (same as V2-S6). */
function checkTerminal(
  pos: Chess,
  fen: string,
  target: "win" | "draw",
  playerColor: "white" | "black",
): GameResult | null {
  // Checkmate: the side to move is checkmated → they lost. Compare to the
  // PLAYER's color (not a hardcoded "white") so a black-player position — a
  // duel/future set could have one — adjudicates correctly.
  if (pos.isCheckmate()) {
    return pos.turn === playerColor ? "fail" : "pass";
  }

  // Stalemate: no legals + not in check → draw.
  if (!pos.isCheck()) {
    const dests = chessgroundDests(pos);
    if (dests.size === 0) {
      return target === "draw" ? "pass" : "fail";
    }
  }

  // Insufficient material → draw.
  if (isInsufficientMaterial(pos)) {
    return target === "draw" ? "pass" : "fail";
  }

  // 50-move rule.
  try {
    const halfmove = parseInt(fen.split(" ")[4], 10);
    if (!isNaN(halfmove) && halfmove >= FIFTY_MOVE_HALFMOVES) {
      return target === "draw" ? "pass" : "fail";
    }
  } catch {
    // Malformed FEN — skip.
  }

  return null;
}

function isInsufficientMaterial(pos: Chess): boolean {
  const board = pos.board;
  const whitePieces = board.white;
  const blackPieces = board.black;

  const whiteHasPawns = !board.pawn.intersect(whitePieces).isEmpty();
  const blackHasPawns = !board.pawn.intersect(blackPieces).isEmpty();
  if (whiteHasPawns || blackHasPawns) return false;

  const whiteRooksQueens = board.rooksAndQueens().intersect(whitePieces).size();
  const blackRooksQueens = board.rooksAndQueens().intersect(blackPieces).size();
  if (whiteRooksQueens > 0 || blackRooksQueens > 0) return false;

  const whiteMinors = whitePieces.size() - 1;
  const blackMinors = blackPieces.size() - 1;

  if (whiteMinors === 0 && blackMinors === 0) return true;
  if (whiteMinors <= 1 && blackMinors === 0) return true;
  if (blackMinors <= 1 && whiteMinors === 0) return true;

  return false;
}

/** Apply a UCI move. Returns the new FEN or null if illegal. */
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

function TrainerForm({
  onSubmit,
}: {
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
          Endgame Self-Tests
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.85rem",
            color: "var(--text-mid)",
          }}
        >
          Win or hold curated endgame positions against the engine — prove your
          technique.
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

function IntroPanel({
  report,
  totalPositions,
  onStart,
}: {
  report: Report | null;
  totalPositions: number;
  onStart: () => void;
}) {
  const pct = report?.stats_block?.endgame_conversion;

  const copyLine =
    pct != null
      ? `You convert ${Math.round(pct * 100)}% of your endgame advantages. These ${totalPositions} curated positions will test your technique — win the winnable, hold the drawable.`
      : `Test your endgame technique against the engine. ${totalPositions} curated positions — win the winnable, hold the drawable.`;

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
          Endgame Self-Tests
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
          {copyLine}
        </p>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-dim)",
          }}
        >
          The engine plays at full strength — no mercy. Win the winning
          positions, hold the draws. No time limit, but longer games count
          against you.
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
          Start — {totalPositions} position{totalPositions !== 1 ? "s" : ""}
        </button>
      </div>
    </div>
  );
}

function SessionComplete({
  tally,
  streak,
  onRestart,
}: {
  tally: { passed: number; failed: number };
  streak: StreakInfo;
  onRestart: () => void;
}) {
  const total = tally.passed + tally.failed;
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      <div
        className="w-full max-w-[400px] text-center"
        style={{
          padding: "2rem",
          borderRadius: "14px",
          border: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <h2
          className="mb-3"
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.5rem",
            fontWeight: 700,
          }}
        >
          Session complete
        </h2>
        <div
          className="mb-3"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.9rem",
            color: "var(--text-mid)",
          }}
        >
          Passed:{" "}
          <span style={{ color: "var(--green)", fontWeight: 600 }}>
            {tally.passed}
          </span>{" "}
          · Failed:{" "}
          <span style={{ color: "var(--coral)", fontWeight: 600 }}>
            {tally.failed}
          </span>
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
            {Math.round((tally.passed / total) * 100)}% pass rate
          </p>
        )}
        {streak.current > 0 && (
          <p
            className="mb-3"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "var(--text-dim)",
            }}
          >
            🔥 {streak.current}-day streak (best {streak.best})
          </p>
        )}
        <button
          onClick={onRestart}
          style={{
            padding: "0.6rem 2rem",
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
          Play again
        </button>
      </div>
    </div>
  );
}

// ── Main trainer component ──────────────────────────────────────────

function EndgamePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const platform = searchParams.get("platform") ?? "";
  const username = searchParams.get("username") ?? "";

  // ── Data state ──────────────────────────────────────────────────
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  // ── Flow state ──────────────────────────────────────────────────
  const [phase, setPhase] = useState<
    "intro" | "playing" | "gameOver" | "sessionComplete"
  >("intro");
  const [posIndex, setPosIndex] = useState(0);

  // ── Game state ──────────────────────────────────────────────────
  const [currentFen, setCurrentFen] = useState("");
  const [engineThinking, setEngineThinking] = useState(false);
  const [gameResult, setGameResult] = useState<GameResult | null>(null);
  const [moveCount, setMoveCount] = useState(0);

  // ── Session tally ───────────────────────────────────────────────
  const [tally, setTally] = useState({ passed: 0, failed: 0 });
  const [user, setUser] = useState<SessionUser | null>(null);
  const [streak, setStreak] = useState<StreakInfo>({ current: 0, best: 0 });

  // ── Refs ────────────────────────────────────────────────────────
  const engineRef = useRef<StockfishWasmEngine | null>(null);
  const posRef = useRef<Chess | null>(null);
  const startTimeRef = useRef(Date.now());
  const playerColorRef = useRef<"white" | "black">("white");
  const targetRef = useRef<"win" | "draw">("win");
  const attemptSubmitted = useRef(false);

  const currentPosition = ENDGAME_SET[posIndex];

  // ── Auth + streak ───────────────────────────────────────────────
  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  useEffect(() => {
    if (user) fetchStreak("endgame").then(setStreak);
  }, [user]);

  // ── Load report (for own-numbers intro) ─────────────────────────
  useEffect(() => {
    if (!platform || !username) return;
    setLoading(true);
    getReport(platform as "chesscom" | "lichess", username)
      .then(setReport)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [platform, username]);

  // ── Engine cleanup ──────────────────────────────────────────────
  useEffect(() => {
    return () => {
      engineRef.current?.close();
    };
  }, []);

  // ── Initialize a position for playout ───────────────────────────
  const initPosition = useCallback(async (position: EndgamePosition) => {
    engineRef.current?.close();

    const setup = parseFen(position.fen);
    if (setup.isErr) return;
    const pos = Chess.fromSetup(setup.unwrap());
    if (pos.isErr) return;
    posRef.current = pos.unwrap();
    setCurrentFen(position.fen);
    setGameResult(null);
    setMoveCount(0);
    attemptSubmitted.current = false;

    playerColorRef.current = position.playerColor;
    targetRef.current = position.target;
    startTimeRef.current = Date.now();

    // Full-strength engine — NO configureStrength call (unlike convert).
    const engine = new StockfishWasmEngine();
    engineRef.current = engine;

    // If the FEN says it's the engine's turn, schedule it.
    const fenTurn = position.fen.split(" ")[1];
    if (fenTurn !== playerColorRef.current[0]) {
      setTimeout(() => doEngineMove(), 300);
    }
  }, []);

  // ── Adjudicate after engine's reply ─────────────────────────────
  //
  //  Called after EVERY engine move. Checks in order per spec:
  //  1. Natural terminal (already checked before this call).
  //  2. target="win"  + mateIn > 0 (player-POV: player mates in N) → pass.
  //  3. target="win"  + playerPovEval >= CONVERTED_CP → pass.
  //  4. target="win"  + playerPovEval <= DRAW_BAND → fail.
  //  5. target="draw" + playerPovEval <= LOST_HOLD_CP → fail.
  //  6. Move cap (30 full moves = 60 halfmoves) with NO resolution →
  //     target="draw" → pass (held); target="win" → fail.
  //
  //  Parameters:
  //    evalCp   — White-POV eval from the engine's search.
  //    mateIn   — player-POV mate distance (negated from engine's search
  //               result since the side-to-move flipped after the engine
  //               moved).  null when the score was centipawns.
  //    halfMoves — total half-moves played this position (used for move cap).
  const adjudicate = useCallback(
    (
      evalCp: number, // White POV
      mateIn: number | null, // player-POV (negated from engine result)
      _currentFen: string,
      halfMoves: number,
    ): GameResult | null => {
      const target = targetRef.current;
      const playerIsBlack = playerColorRef.current === "black";

      // playerPovEval: White-POV evalCp, signed for the player.
      const playerPovEval = playerIsBlack ? -evalCp : evalCp;

      // mateIn is now player-POV (negated by caller): > 0 = player mates.
      if (target === "win" && mateIn != null && mateIn > 0) {
        return "pass";
      }

      // Eval-based adjudication.
      if (target === "win") {
        if (playerPovEval >= CONVERTED_CP) return "pass";
        if (playerPovEval <= DRAW_BAND) return "fail";
      } else {
        // target === "draw"
        if (playerPovEval <= LOST_HOLD_CP) return "fail";
      }

      // Move cap is the LAST check — only fires when nothing else resolved.
      // 30 full moves = 60 halfmoves.
      if (halfMoves / 2 >= MOVE_CAP) {
        return target === "draw" ? "pass" : "fail";
      }

      return null;
    },
    [],
  );

  // ── Engine move ─────────────────────────────────────────────────
  const doEngineMove = useCallback(async () => {
    const engine = engineRef.current;
    const pos = posRef.current;
    if (!engine || !pos) return;

    setEngineThinking(true);

    try {
      const fen = makeFen(pos.toSetup());
      const result = await engine.evaluate(fen, {
        movetimeMs: ENGINE_MOVETIME_MS,
      });
      const newFen = applyMove(pos, result.bestMoveUci);
      if (!newFen) {
        // Engine gave an illegal move — pass for the player.
        setGameResult("pass");
        setEngineThinking(false);
        return;
      }
      setCurrentFen(newFen);
      setMoveCount((c) => c + 1);

      // Check natural terminal.
      const terminal = checkTerminal(pos, newFen, targetRef.current, playerColorRef.current);
      if (terminal) {
        setGameResult(terminal);
        setEngineThinking(false);
        return;
      }

      // Eval adjudication.
      // mateIn from result is engine-POV (the engine searched the pre-move
      // position where it was to move).  After the engine's move, the player
      // is now to move — negate so mateIn > 0 means the PLAYER mates.
      const adjudicated = adjudicate(
        result.evalCp,
        result.mateIn != null ? -result.mateIn : null,
        newFen,
        moveCount + 1,
      );
      if (adjudicated) {
        setGameResult(adjudicated);
        setEngineThinking(false);
        return;
      }
    } catch (err) {
      console.error("Engine move failed:", err);
      setGameResult("pass");
    } finally {
      setEngineThinking(false);
    }
  }, [adjudicate, moveCount]);

  // ── Handle user move ────────────────────────────────────────────
  const handleUserMove = useCallback(
    (move: BoardMove) => {
      if (gameResult || engineThinking) return;

      const pos = posRef.current;
      if (!pos) return;

      const uci = move.from + move.to + (move.promotion ?? "");
      const newFen = applyMove(pos, uci);
      if (!newFen) return;

      setCurrentFen(newFen);
      setMoveCount((c) => c + 1);

      // Check terminal after user's move.
      const terminal = checkTerminal(pos, newFen, targetRef.current, playerColorRef.current);
      if (terminal) {
        setGameResult(terminal);
        return;
      }

      // Schedule engine's reply.
      // Set engineThinking immediately to prevent double-moves.
      setEngineThinking(true);
      setTimeout(() => doEngineMove(), 100);
    },
    [gameResult, engineThinking, doEngineMove],
  );

  // ── Give up ─────────────────────────────────────────────────────
  const handleGiveUp = useCallback(() => {
    if (gameResult) return;
    setGameResult("fail");
  }, [gameResult]);

  // ── Submit attempt when game ends ───────────────────────────────
  useEffect(() => {
    if (!gameResult || !currentPosition || attemptSubmitted.current) return;
    attemptSubmitted.current = true;

    const seconds = Math.round((Date.now() - startTimeRef.current) / 1000);

    if (user) {
      submitAttempt({
        refId: currentPosition.id,
        refType: "curated",
        trainer: "endgame",
        grade: gameResult, // "pass" | "fail"
        seconds,
      }).then((s) => {
        if (s) setStreak(s);
      });
    }

    setTally((t) => {
      if (gameResult === "pass") return { ...t, passed: t.passed + 1 };
      return { ...t, failed: t.failed + 1 };
    });
  }, [gameResult, currentPosition, user]);

  // ── Next position ───────────────────────────────────────────────
  const handleNext = useCallback(() => {
    const nextIndex = posIndex + 1;
    if (nextIndex >= ENDGAME_SET.length) {
      engineRef.current?.close();
      setPhase("sessionComplete");
      return;
    }
    setPosIndex(nextIndex);
    setGameResult(null);
  }, [posIndex]);

  // Initialize position when posIndex changes.
  useEffect(() => {
    const position = ENDGAME_SET[posIndex];
    if (!position || phase !== "playing") return;
    initPosition(position);
  }, [posIndex, phase, initPosition]);

  // ── Start playing ───────────────────────────────────────────────
  const handleStart = useCallback(() => {
    setPhase("playing");
    setTally({ passed: 0, failed: 0 });
    if (ENDGAME_SET.length > 0) {
      initPosition(ENDGAME_SET[0]);
    }
  }, [initPosition]);

  // ── Restart session ─────────────────────────────────────────────
  const handleRestart = useCallback(() => {
    setPhase("intro");
    setPosIndex(0);
    setTally({ passed: 0, failed: 0 });
    setGameResult(null);
  }, []);

  // ── Render states ───────────────────────────────────────────────

  if (!platform || !username) {
    return (
      <TrainerForm
        onSubmit={(p, u) =>
          router.push(
            `/train/endgame?platform=${encodeURIComponent(p)}&username=${encodeURIComponent(u.trim())}`,
          )
        }
      />
    );
  }

  if (loading) {
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

  if (phase === "intro") {
    return (
      <IntroPanel
        report={report}
        totalPositions={ENDGAME_SET.length}
        onStart={handleStart}
      />
    );
  }

  if (phase === "sessionComplete") {
    return (
      <SessionComplete
        tally={tally}
        streak={streak}
        onRestart={handleRestart}
      />
    );
  }

  // ── Playing or game-over phase ──────────────────────────────────

  const isPlayerTurn =
    !gameResult &&
    !engineThinking &&
    currentFen.split(" ")[1] === playerColorRef.current[0];

  const resultLabel: Record<
    GameResult,
    { text: string; color: string; bg: string }
  > = {
    pass: { text: "Passed", color: "var(--green)", bg: "var(--green-bg)" },
    fail: { text: "Failed", color: "var(--coral)", bg: "var(--coral-bg)" },
  };

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
          {posIndex + 1} / {ENDGAME_SET.length}
        </span>
        <span className="flex gap-3">
          <span style={{ color: "var(--green)" }}>{tally.passed}P</span>
          <span style={{ color: "var(--coral)" }}>{tally.failed}F</span>
        </span>
        {streak.current > 0 && <span>🔥{streak.current}</span>}
      </div>

      {/* Position info */}
      <div
        className="w-full max-w-[560px] mb-1"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.6rem",
          color: "var(--text-dim)",
        }}
      >
        {currentPosition.pattern ?? "Endgame"} · Target:{" "}
        {currentPosition.target === "win" ? "Win" : "Hold draw"} · You are{" "}
        {playerColorRef.current === "white" ? "White" : "Black"}
      </div>

      {/* Board */}
      <Board
        fen={currentFen}
        orientation={playerColorRef.current}
        interactable={isPlayerTurn}
        onMove={handleUserMove}
        ariaLabel={`Endgame position ${posIndex + 1} of ${ENDGAME_SET.length} as ${playerColorRef.current}`}
      />

      {/* Engine thinking indicator */}
      {engineThinking && (
        <div
          className="w-full max-w-[560px] mt-2 text-center"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "0.7rem",
            color: "var(--text-dim)",
          }}
        >
          Engine thinking…
        </div>
      )}

      {/* Status: whose turn */}
      {!gameResult && !engineThinking && (
        <div
          className="w-full max-w-[560px] mt-2 text-center"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-mid)",
          }}
        >
          {isPlayerTurn
            ? "Your turn"
            : currentPosition.target === "draw"
              ? "Hold the draw…"
              : "Win this…"}
        </div>
      )}

      {/* Give up button */}
      {!gameResult && (
        <button
          onClick={handleGiveUp}
          className="mt-3"
          style={{
            padding: "0.35rem 1rem",
            borderRadius: "6px",
            border: "1px solid var(--border)",
            backgroundColor: "transparent",
            color: "var(--text-dim)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.65rem",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            cursor: "pointer",
          }}
        >
          Give up
        </button>
      )}

      {/* Game-over result panel */}
      {gameResult && (
        <div
          className="w-full max-w-[560px] mt-3"
          style={{
            padding: "1rem",
            borderRadius: "10px",
            border: `1px solid ${resultLabel[gameResult].color}`,
            backgroundColor: resultLabel[gameResult].bg,
            fontFamily: "var(--font-sans)",
            fontSize: "0.9rem",
            textAlign: "center",
          }}
        >
          <div
            className="mb-2"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "1rem",
              fontWeight: 600,
              color: resultLabel[gameResult].color,
            }}
          >
            {resultLabel[gameResult].text}
          </div>
          <p
            style={{
              fontSize: "0.8rem",
              color: "var(--text-mid)",
              marginBottom: "0.75rem",
            }}
          >
            {gameResult === "pass"
              ? currentPosition.target === "win"
                ? "You converted — the technique held up."
                : "You held the draw — solid defense."
              : currentPosition.target === "win"
                ? `Not converted — ${currentPosition.why.split(".")[0]}.`
                : `Lost the hold — ${currentPosition.why.split(".")[0]}.`}
          </p>
          <p
            style={{
              fontSize: "0.7rem",
              color: "var(--text-dim)",
              marginBottom: "0.75rem",
              lineHeight: 1.5,
            }}
          >
            {currentPosition.why}
          </p>
          {posIndex + 1 < ENDGAME_SET.length ? (
            <button
              onClick={handleNext}
              style={{
                padding: "0.5rem 1.5rem",
                borderRadius: "8px",
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
              Next position
            </button>
          ) : (
            <button
              onClick={() => {
                engineRef.current?.close();
                setPhase("sessionComplete");
              }}
              style={{
                padding: "0.5rem 1.5rem",
                borderRadius: "8px",
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
              See results
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Suspense boundary ─────────────────────────────────────────────

export default function EndgamePage() {
  return (
    <Suspense
      fallback={
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
            Loading…
          </p>
        </div>
      }
    >
      <EndgamePageInner />
    </Suspense>
  );
}
