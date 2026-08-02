"use client";
// V2-S4: Trainer API helpers — fetch positions, submit attempts, fetch streak.

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PositionItem {
  id: string;
  fen: string;
  best_line_uci: string;
  ply: number;
  eval_before_cp: number;
  game_url: string;
  played_at: string | null;
  opponent_move_san: string | null;
  opponent_move_uci: string | null;
}

export async function fetchRetryPositions(
  platform: string,
  username: string,
  category: string = "blunder",
  limit: number = 10,
  gameUrls?: string[],
): Promise<PositionItem[]> {
  try {
    const params = new URLSearchParams({
      platform,
      username,
      category,
      limit: String(limit),
    });
    if (gameUrls && gameUrls.length > 0) {
      params.set("game_urls", gameUrls.join(","));
    }
    const resp = await fetch(
      `${BACKEND}/api/train/positions?${params}`
    );
    if (!resp.ok) return [];
    return resp.json();
  } catch {
    return [];
  }
}

export interface StreakInfo {
  current: number;
  best: number;
}

export async function submitAttempt(params: {
  refId: string;
  refType?: string;
  trainer: string;
  grade: string;
  seconds: number;
}): Promise<StreakInfo | null> {
  try {
    const resp = await fetch(`${BACKEND}/api/train/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ref_id: params.refId,
        ref_type: params.refType ?? "position",
        trainer: params.trainer,
        grade: params.grade,
        seconds: params.seconds,
      }),
      credentials: "include",
    });
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}

export async function fetchStreak(
  trainer: string
): Promise<StreakInfo> {
  try {
    const resp = await fetch(
      `${BACKEND}/api/train/streak?trainer=${encodeURIComponent(trainer)}`,
      { credentials: "include" }
    );
    if (!resp.ok) return { current: 0, best: 0 };
    return resp.json();
  } catch {
    return { current: 0, best: 0 };
  }
}

// ── V2-S12: Training progress ────────────────────────────────────────

export interface TrainerProgress {
  attempts: number;
  perfect: number;
  pass: number;
  fail: number;
  current_streak: number;
  best_streak: number;
}

export async function fetchProgress(since?: string): Promise<Record<string, TrainerProgress> | null> {
  try {
    const url = new URL(`${BACKEND}/api/train/progress`);
    // URLSearchParams.set() correctly encodes the + in ISO timezone offsets.
    if (since) url.searchParams.set("since", since);
    const resp = await fetch(url.toString(), {
      credentials: "include",
    });
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}
