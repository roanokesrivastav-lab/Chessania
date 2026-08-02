"use client";
// V2-S2: Guest anon-id cookie + session helper.
// Anon ID: a random string stored in a cookie so guest progress can be
// adopted when the user later signs in. This is NOT the session cookie —
// the session cookie is httpOnly and managed by the backend.

const ANON_ID_COOKIE = "chessania_anon_id";

function generateAnonId(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export function getAnonId(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${ANON_ID_COOKIE}=([^;]*)`)
  );
  if (match) return match[1];

  const id = generateAnonId();
  document.cookie = `${ANON_ID_COOKIE}=${id};path=/;max-age=${60 * 60 * 24 * 365};SameSite=Lax`;
  return id;
}

export interface SessionUser {
  id: string;
  display_name: string;
  email: string | null;
  lichess_id: string | null;
}

export interface SessionResponse {
  user: SessionUser | null;
}

const BACKEND =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getSession(): Promise<SessionResponse> {
  try {
    const resp = await fetch(`${BACKEND}/api/auth/me`, {
      credentials: "include",
    });
    if (!resp.ok) return { user: null };
    return resp.json();
  } catch {
    return { user: null };
  }
}

export async function requestMagicLink(email: string): Promise<boolean> {
  try {
    const resp = await fetch(`${BACKEND}/api/auth/magic-link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function logout(): Promise<boolean> {
  try {
    const resp = await fetch(`${BACKEND}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

export function getLichessStartUrl(): string {
  return `${BACKEND}/api/auth/lichess/start`;
}
