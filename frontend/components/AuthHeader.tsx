"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSession, logout, type SessionUser } from "@/lib/auth";

export default function AuthHeader() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined);

  useEffect(() => {
    getSession().then((s) => setUser(s.user));
  }, []);

  const handleLogout = async () => {
    const ok = await logout();
    if (ok) setUser(null);
  };

  // Loading skeleton — don't flash the sign-in link on load.
  if (user === undefined) {
    return (
      <div
        style={{
          padding: "0.5rem 1rem",
          display: "flex",
          justifyContent: "flex-end",
          fontFamily: "var(--font-sans)",
          fontSize: "0.85rem",
          color: "var(--text-dim)",
        }}
      >
        …
      </div>
    );
  }

  if (user === null) {
    return (
      <div
        style={{
          padding: "0.5rem 1rem",
          display: "flex",
          justifyContent: "flex-end",
          fontFamily: "var(--font-sans)",
          fontSize: "0.85rem",
        }}
      >
        <Link
          href="/login"
          style={{
            color: "var(--gold)",
            textDecoration: "none",
            fontFamily: "var(--font-mono)",
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          Sign in to save progress
        </Link>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "0.5rem 1rem",
        display: "flex",
        justifyContent: "flex-end",
        alignItems: "center",
        gap: "0.75rem",
        fontFamily: "var(--font-sans)",
        fontSize: "0.85rem",
      }}
    >
      <span
        style={{
          color: "var(--text-mid)",
          fontFamily: "var(--font-serif)",
          fontSize: "0.9rem",
        }}
      >
        {user.display_name}
      </span>
      <button
        onClick={handleLogout}
        style={{
          background: "none",
          border: "none",
          color: "var(--text-dim)",
          cursor: "pointer",
          fontFamily: "var(--font-mono)",
          fontSize: "0.7rem",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          padding: 0,
        }}
      >
        Sign out
      </button>
    </div>
  );
}
