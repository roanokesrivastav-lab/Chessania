"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Board from "@/components/board/Board";
import type { BoardMove } from "@/components/board/Board";
import { Chess } from "chessops/chess";
import { parseFen, makeFen } from "chessops/fen";
import { parseUci } from "chessops";
import { chessgroundDests } from "chessops/compat";
import type { SquareName } from "chessops/types";
import { StockfishWasmEngine } from "@/lib/engine";
import { getSession } from "@/lib/auth";
import type { SessionUser } from "@/lib/auth";
import {
  fetchRetryPositions,
  submitAttempt,
  fetchStreak,
  type PositionItem,
  type StreakInfo,
} from "@/lib/train";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";

// ── Constants ────────────────────────────────────────────────────────

/** Stockfish's UCI_Elo supported range (confirmed against stockfish-18-lite-single). */
const SF_ELO_MIN = 1320;
const SF_ELO_MAX = 3190;

/** Engine movetime for opponent moves (ms). */
const ENGINE_MOVETIME_MS = 500;

/** Halfmove clock threshold for the 50-move rule (100 halfmoves = 50 full moves). */
const FIFTY_MOVE_HALFMOVES = 100;

// ── Types ────────────────────────────────────────────────────────────

type GameResult = "win" | "loss" | "draw" | "resign";

// ── Helpers ──────────────────────────────────────────────────────────

/** Clamp the player's rating to Stockfish's supported Elo range. */
function clampElo(rating: number | null | undefined): number {
  if (rating == null) return SF_ELO_MIN;
  return Math.max(SF_ELO_MIN, Math.min(SF_ELO_MAX, Math.round(rating)));
}

/** Check if the position is terminal (checkmate / stalemate / 50-move rule /
 *  insufficient material).
 *
 *  NOTE: Threefold repetition is explicitly OUT of scope for V2-S6 (DoD).
 *  The Resign button is the escape hatch for dragging games. If the same
 *  position appears three times, the player must either convert or resign —
 *  the engine won't auto-draw on repetition. */
function checkTerminal(
  pos: Chess,
  fen: string,
  playerColor: "white" | "black",
): GameResult | null {
  // Checkmate: the side to move is checkmated → they lost. Compare to the
  // PLAYER's color (not a hardcoded "white") — unconverted positions can have
  // the player as Black, so this must not assume White or it inverts win/loss.
  if (pos.isCheckmate()) {
    return pos.turn === playerColor ? "loss" : "win";
  }

  // Stalemate: the side to move has no legal moves but is not in check → draw.
  if (!pos.isCheck()) {
    const dests = chessgroundDests(pos);
    if (dests.size === 0) return "draw";
  }

  // Insufficient material: both sides lack mating material.
  if (isInsufficientMaterial(pos)) return "draw";

  // 50-move rule: halfmove clock (FEN field 5) ≥ 100.
  try {
    const halfmove = parseInt(fen.split(" ")[4], 10);
    if (!isNaN(halfmove) && halfmove >= FIFTY_MOVE_HALFMOVES) return "draw";
  } catch {
    // Malformed FEN — skip this check.
  }

  return null; // Game still in progress.
}

/** Simple insufficient-material check: KvK, or K+minor vs K. Does not detect
 *  the same-color-bishops nuance (K+B vs K+B) — that case falls through to
 *  the 50-move rule instead, which still ends the game correctly, just later. */
function isInsufficientMaterial(pos: Chess): boolean {
  const board = pos.board;
  const whitePieces = board.white;
  const blackPieces = board.black;

  const whiteHasPawns = !board.pawn.intersect(whitePieces).isEmpty();
  const blackHasPawns = !board.pawn.intersect(blackPieces).isEmpty();
  if (whiteHasPawns || blackHasPawns) return false; // Pawns can promote.

  const whiteRooksQueens = board.rooksAndQueens().intersect(whitePieces).size();
  const blackRooksQueens = board.rooksAndQueens().intersect(blackPieces).size();
  if (whiteRooksQueens > 0 || blackRooksQueens > 0) return false; // Major pieces can mate.

  const whiteMinors = whitePieces.size() - 1; // minus king
  const blackMinors = blackPieces.size() - 1; // minus king

  // K vs K
  if (whiteMinors === 0 && blackMinors === 0) return true;
  // K+minor vs K
  if (whiteMinors <= 1 && blackMinors === 0) return true;
  if (blackMinors <= 1 && whiteMinors === 0) return true;
  // K+minor vs K+minor (same-color bishops is insufficient but we skip that nuance)

  return false;
}

/**
 * Apply a UCI move to a Chess position. Returns the new FEN or null if the
 * move is illegal/invalid.
 */
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

/** Derive player color from a FEN. The FEN is fen_before the player's move,
 *  so the side-to-move IS the player's color. */
function playerColorFromFen(fen: string): "white" | "black" {
  const parts = fen.split(" ");
  return parts[1] === "w" ? "white" : "black";
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
          Advantage Capitalization
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.85rem",
            color: "var(--text-mid)",
          }}
        >
          Play out your unconverted winning positions against the engine —
          prove you can close the deal.
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

function LoadingState() {
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

function EmptyState() {
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
          No unconverted positions yet
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.9rem",
            color: "var(--text-mid)",
          }}
        >
          Run a v1 analysis first to mine unconverted positions from your
          games — positions where you had a winning advantage but didn&rsquo;t
          close it out.
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

function IntroPanel({
  report,
  totalPositions,
  onStart,
}: {
  report: Report | null;
  totalPositions: number;
  onStart: () => void;
}) {
  const pct = report?.stats_block?.advantage_capitalization;
  const rating = report?.player_summary?.rating;

  const copyLine =
    pct != null
      ? `You convert ${Math.round(pct * 100)}% of your winning positions — these ${totalPositions} unconverted games are the ones that got away.`
      : `You have ${totalPositions} unconverted winning positions in your bank. Time to close the deal.`;

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
          Advantage Capitalization
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
        {rating != null && (
          <p
            className="mb-4"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              color: "var(--text-dim)",
            }}
          >
            Opponent strength: {clampElo(rating)} Elo (your rating, capped)
          </p>
        )}
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-dim)",
          }}
        >
          You&rsquo;ll play each position from your side against the engine.
          Win = converted. Draw/loss/resign = not yet.
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

// ── Main trainer component ──────────────────────────────────────────

function ConvertPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const platform = searchParams.get("platform") ?? "";
  const username = searchParams.get("username") ?? "";

  // V2-S7: optional game-urls filter from deep links.
  const gamesParam = searchParams.get("games") ?? "";
  const gameUrls: string[] | undefined = gamesParam
    ? gamesParam.split(",").filter(Boolean)
    : undefined;
  const wasFiltered = gameUrls !== undefined && gameUrls.length > 0;

  // ── Data state ──────────────────────────────────────────────────
  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  // ── Flow state ──────────────────────────────────────────────────
  const [phase, setPhase] = useState<"intro" | "playing" | "gameOver" | "sessionComplete">("intro");
  const [posIndex, setPosIndex] = useState(0);

  // ── Game state ──────────────────────────────────────────────────
  const [currentFen, setCurrentFen] = useState("");
  const [engineThinking, setEngineThinking] = useState(false);
  const [gameResult, setGameResult] = useState<GameResult | null>(null);
  const [fallbackNote, setFallbackNote] = useState(false);
  const [moveCount, setMoveCount] = useState(0);

  // ── Session tally ───────────────────────────────────────────────
  const [tally, setTally] = useState({ converted: 0, failed: 0 });
  const [user, setUser] = useState<SessionUser | null>(null);
  const [streak, setStreak] = useState<StreakInfo>({ current: 0, best: 0 });

  // ── Refs ────────────────────────────────────────────────────────
  const engineRef = useRef<StockfishWasmEngine | null>(null);
  const posRef = useRef<Chess | null>(null);
  const startTimeRef = useRef(Date.now());
  const playerColorRef = useRef<"white" | "black">("white");
  const attemptSubmitted = useRef(false);

  const currentPosition = positions[posIndex];

  // ── Auth + streak ───────────────────────────────────────────────
  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  useEffect(() => {
    if (user) fetchStreak("convert").then(setStreak);
  }, [user]);

  // ── Load data ───────────────────────────────────────────────────
  useEffect(() => {
    if (!platform || !username) {
      setLoading(false);
      return;
    }
    Promise.all([
      fetchRetryPositions(platform, username, "unconverted", 10, gameUrls),
      getReport(platform as "chesscom" | "lichess", username).catch(() => null),
    ]).then(([posData, reportData]) => {
      // V2-S7: if we had a game filter and it returned empty, fall back.
      if (wasFiltered && posData.length === 0) {
        fetchRetryPositions(platform, username, "unconverted").then((unfiltered) => {
          setPositions(unfiltered);
          setFallbackNote(true);
          setReport(reportData);
          setLoading(false);
        });
        return;
      }
      setPositions(posData);
      setReport(reportData);
      setLoading(false);
    });
  }, [platform, username, gameUrls, wasFiltered]);

  // ── Engine cleanup ──────────────────────────────────────────────
  useEffect(() => {
    return () => {
      engineRef.current?.close();
    };
  }, []);

  // ── Initialize a position for playout ───────────────────────────
  const initPosition = useCallback(
    async (position: PositionItem) => {
      // Close previous engine.
      engineRef.current?.close();

      // Parse the starting FEN.
      const setup = parseFen(position.fen);
      if (setup.isErr) return;
      const pos = Chess.fromSetup(setup.unwrap());
      if (pos.isErr) return;
      posRef.current = pos.unwrap();
      setCurrentFen(position.fen);
      setGameResult(null);
      setMoveCount(0);
      attemptSubmitted.current = false;

      playerColorRef.current = playerColorFromFen(position.fen);
      startTimeRef.current = Date.now();

      // Create and configure the engine.
      const engine = new StockfishWasmEngine();
      engineRef.current = engine;

      try {
        const elo = clampElo(report?.player_summary?.rating);
        await engine.configureStrength(elo);
      } catch (err) {
        console.error("Failed to configure engine strength:", err);
        // Engine will still work at default strength.
      }

      // For unconverted positions, the fen_before has the player's
      // color to move — it's always the player's turn first.
      // Edge case: if the FEN says it's the engine's turn, schedule it.
      const fenTurn = position.fen.split(" ")[1];
      if (fenTurn !== playerColorRef.current[0]) {
        setTimeout(() => doEngineMove(), 300);
      }
    },
    [report],
  );



  // ── Engine move ─────────────────────────────────────────────────
  const doEngineMove = useCallback(async () => {
    const engine = engineRef.current;
    const pos = posRef.current;
    if (!engine || !pos) return;

    setEngineThinking(true);

    try {
      const fen = makeFen(pos.toSetup());
      const result = await engine.evaluate(fen, { movetimeMs: ENGINE_MOVETIME_MS });
      const newFen = applyMove(pos, result.bestMoveUci);
      if (!newFen) {
        // Engine gave an illegal move — treat as a win for the player.
        setGameResult("win");
        setEngineThinking(false);
        return;
      }
      setCurrentFen(newFen);
      setMoveCount((c) => c + 1);

      // Check terminal after engine's move.
      const terminal = checkTerminal(pos, newFen, playerColorRef.current);
      if (terminal) {
        setGameResult(terminal);
        setEngineThinking(false);
        return;
      }
    } catch (err) {
      console.error("Engine move failed:", err);
      // Treat engine failure as a win for the player.
      setGameResult("win");
    } finally {
      setEngineThinking(false);
    }
  }, []);

  // ── Handle user move ────────────────────────────────────────────
  const handleUserMove = useCallback(
    (move: BoardMove) => {
      if (gameResult || engineThinking) return;

      const pos = posRef.current;
      if (!pos) return;

      const uci = move.from + move.to + (move.promotion ?? "");
      const newFen = applyMove(pos, uci);
      if (!newFen) return; // Illegal move — Board already rejects these, but be safe.

      setCurrentFen(newFen);
      setMoveCount((c) => c + 1);

      // Check terminal after user's move.
      const terminal = checkTerminal(pos, newFen, playerColorRef.current);
      if (terminal) {
        setGameResult(terminal);
        return;
      }

      // Schedule engine's reply.
      setTimeout(() => doEngineMove(), 100);
    },
    [gameResult, engineThinking],
  );

  // ── Resign ──────────────────────────────────────────────────────
  const handleResign = useCallback(() => {
    if (gameResult) return;
    setGameResult("resign");
  }, [gameResult]);

  // ── Submit attempt when game ends ───────────────────────────────
  useEffect(() => {
    if (!gameResult || !currentPosition || attemptSubmitted.current) return;
    attemptSubmitted.current = true;

    const grade = gameResult === "win" ? "pass" : "fail";
    const seconds = Math.round((Date.now() - startTimeRef.current) / 1000);

    if (user) {
      submitAttempt({
        refId: currentPosition.id,
        trainer: "convert",
        grade,
        seconds,
      }).then((s) => {
        if (s) setStreak(s);
      });
    }

    // Update tally.
    setTally((t) => {
      if (gameResult === "win") return { ...t, converted: t.converted + 1 };
      return { ...t, failed: t.failed + 1 };
    });
  }, [gameResult, currentPosition, user]);

  // ── Next position ───────────────────────────────────────────────
  const handleNext = useCallback(() => {
    const nextIndex = posIndex + 1;
    if (nextIndex >= positions.length) {
      engineRef.current?.close();
      setPhase("sessionComplete");
      return;
    }
    setPosIndex(nextIndex);
    setGameResult(null);
    // initPosition will be called via the effect below.
  }, [posIndex, positions.length]);

  // Initialize position when posIndex changes.
  useEffect(() => {
    const position = positions[posIndex];
    if (!position || phase !== "playing") return;
    initPosition(position);
  }, [posIndex, phase, positions, initPosition]);

  // ── Start playing ───────────────────────────────────────────────
  const handleStart = useCallback(() => {
    setPhase("playing");
    setTally({ converted: 0, failed: 0 });
    // Directly init the first position rather than relying on the
    // useEffect cascade (which may not fire if posIndex is already 0).
    if (positions.length > 0) {
      initPosition(positions[0]);
    }
  }, [positions, initPosition]);

  // ── Restart session ─────────────────────────────────────────────
  const handleRestart = useCallback(() => {
    setPhase("intro");
    setPosIndex(0);
    setTally({ converted: 0, failed: 0 });
    setGameResult(null);
  }, []);

  // ── Render states ───────────────────────────────────────────────

  if (!platform || !username) {
    return (
      <TrainerForm
        onSubmit={(p, u) =>
          router.push(
            `/train/convert?platform=${encodeURIComponent(p)}&username=${encodeURIComponent(u.trim())}`,
          )
        }
      />
    );
  }

  if (loading) return <LoadingState />;
  if (positions.length === 0) return <EmptyState />;

  if (phase === "intro") {
    return (
      <IntroPanel
        report={report}
        totalPositions={positions.length}
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
    (currentFen.split(" ")[1] === playerColorRef.current[0]);

  const resultLabel: Record<GameResult, { text: string; color: string; bg: string }> = {
    win: { text: "Converted!", color: "var(--green)", bg: "var(--green-bg)" },
    loss: { text: "Lost", color: "var(--coral)", bg: "var(--coral-bg)" },
    draw: { text: "Drawn", color: "var(--text-dim)", bg: "var(--surface-2)" },
    resign: { text: "Resigned", color: "var(--text-dim)", bg: "var(--surface-2)" },
  };

  return (
    <div
      className="flex min-h-screen flex-col items-center p-4"
      style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}
    >
      {fallbackNote && (
        <div
          className="w-full max-w-[560px] mb-3"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "0.8rem",
            color: "var(--text-dim)",
            padding: "0.5rem 0.75rem",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            backgroundColor: "var(--surface-2)",
            textAlign: "center",
          }}
        >
          No drills from those specific games — here&rsquo;s your full bank instead.
        </div>
      )}

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
          {posIndex + 1} / {positions.length}
        </span>
        <span className="flex gap-3">
          <span style={{ color: "var(--green)" }}>{tally.converted}C</span>
          <span style={{ color: "var(--coral)" }}>{tally.failed}F</span>
        </span>
        {streak.current > 0 && <span>🔥{streak.current}</span>}
      </div>

      {/* Source position info */}
      <div
        className="w-full max-w-[560px] mb-1"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.6rem",
          color: "var(--text-dim)",
        }}
      >
        Position {posIndex + 1} · You are{" "}
        {playerColorRef.current === "white" ? "White" : "Black"}
        {currentPosition.game_url && (
          <>
            {" "}
            ·{" "}
            <a
              href={currentPosition.game_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "var(--text-dim)", textDecoration: "none" }}
            >
              View source game ↗
            </a>
          </>
        )}
      </div>

      {/* Board */}
      <Board
        fen={currentFen}
        orientation={playerColorRef.current}
        interactable={isPlayerTurn}
        onMove={handleUserMove}
        ariaLabel={`Convert position ${posIndex + 1} of ${positions.length} as ${playerColorRef.current}`}
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
          Opponent thinking…
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
          {isPlayerTurn ? "Your turn" : ""}
        </div>
      )}

      {/* Resign button */}
      {!gameResult && (
        <button
          onClick={handleResign}
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
          Resign
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
            {gameResult === "win"
              ? "You converted — the advantage wasn't wasted this time."
              : gameResult === "draw"
                ? "The game fizzled. A won position needs a forcing plan."
                : "This one got away — the engine held or turned it around."}
          </p>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.65rem",
              color: "var(--text-dim)",
              marginBottom: "0.75rem",
            }}
          >
            {moveCount} move{moveCount !== 1 ? "s" : ""} played
          </p>
          <button
            onClick={handleNext}
            style={{
              padding: "0.4rem 1.5rem",
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
            Next{posIndex + 1 >= positions.length ? " — Finish" : ""} →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Session complete ────────────────────────────────────────────────

function SessionComplete({
  tally,
  streak,
  onRestart,
}: {
  tally: { converted: number; failed: number };
  streak: StreakInfo;
  onRestart: () => void;
}) {
  const total = tally.converted + tally.failed;
  const pct = total > 0 ? Math.round((tally.converted / total) * 100) : 0;

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
          className="mb-2"
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.5rem",
            fontWeight: 700,
          }}
        >
          Session complete!
        </h2>
        <p
          className="mb-4"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "1.5rem",
            fontWeight: 700,
            color: "var(--gold)",
          }}
        >
          {pct}% converted
        </p>
        <div className="flex justify-center gap-6 mb-4">
          <ResultChip label="Converted" count={tally.converted} color="var(--green)" bg="var(--green-bg)" />
          <ResultChip label="Failed" count={tally.failed} color="var(--coral)" bg="var(--coral-bg)" />
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

// ── Page export ──────────────────────────────────────────────────────

export default function ConvertPage() {
  return (
    <Suspense fallback={null}>
      <ConvertPageInner />
    </Suspense>
  );
}
