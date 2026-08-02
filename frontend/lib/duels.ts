"use client";
// V2-S10: Position Duels — create a Lichess challenge from a FEN.

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface CreateDuelParams {
  fen: string;
  source: "paste" | "curated-mate" | "curated-endgame";
  mode: "realtime" | "correspondence";
  clockLimitS?: number;
  clockIncrementS?: number;
  days?: number;
  name?: string;
}

export interface DuelResponse {
  id: string;
  challenge_id: string;
  url: string;
  urlWhite: string;
  urlBlack: string;
}

export type { DuelResponse as Duel };

export async function createDuel(
  params: CreateDuelParams,
): Promise<DuelResponse> {
  const resp = await fetch(`${BACKEND}/api/duels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fen: params.fen,
      source: params.source,
      mode: params.mode,
      clock_limit_s: params.clockLimitS,
      clock_increment_s: params.clockIncrementS,
      days: params.days,
      name: params.name,
    }),
    credentials: "include",
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      body.detail || "Could not create the duel — please try again.",
    );
  }

  return resp.json();
}

// ── V2-S11: Duel history ─────────────────────────────────────────────

export interface DuelHistoryItem {
  id: string;
  fen: string;
  source: string;
  url: string;
  urlWhite: string;
  urlBlack: string;
  created_at: string | null;
}

export async function listMyDuels(): Promise<DuelHistoryItem[]> {
  try {
    const resp = await fetch(`${BACKEND}/api/duels`, {
      credentials: "include",
    });
    if (!resp.ok) return [];
    return resp.json();
  } catch {
    return [];
  }
}
