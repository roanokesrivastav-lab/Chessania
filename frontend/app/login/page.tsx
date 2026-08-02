"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getAnonId, getLichessStartUrl, getSession, requestMagicLink } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "sent">("idle");
  const [checking, setChecking] = useState(true);

  // Ensure anon-id exists on first visit.
  useEffect(() => {
    getAnonId();
  }, []);

  // If already signed in, redirect to /train.
  useEffect(() => {
    getSession().then((s) => {
      if (s.user) {
        router.replace("/train");
      } else {
        setChecking(false);
      }
    });
  }, [router]);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setState("loading");
    await requestMagicLink(email.trim());
    setState("sent");
  };

  const handleLichessSignIn = async () => {
    try {
      const resp = await fetch(getLichessStartUrl(), {
        credentials: "include",
      });
      if (!resp.ok) return;
      const { url } = await resp.json();
      window.location.href = url;
    } catch {
      // Silently fail.
    }
  };

  if (checking) return null;

  const errorMessages: Record<string, string> = {
    invalid_link: "That sign-in link is invalid or has already been used.",
    oauth_expired: "The Lichess sign-in session expired — please try again.",
    oauth_mismatch: "Something went wrong with Lichess sign-in — please try again.",
    oauth_failed: "Could not complete Lichess sign-in — please try again.",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        backgroundColor: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          padding: "2rem",
          borderRadius: "14px",
          border: "1px solid var(--border)",
          backgroundColor: "var(--surface)",
          boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
        }}
      >
        {/* Heading */}
        <h1
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "1.75rem",
            fontWeight: 700,
            margin: "0 0 0.5rem 0",
            color: "var(--text)",
            textWrap: "balance",
          }}
        >
          Sign in to Chessania
        </h1>
        <p
          style={{
            fontSize: "0.9rem",
            color: "var(--text-mid)",
            margin: "0 0 1.5rem 0",
          }}
        >
          Save your training progress across sessions.
        </p>

        {/* Error banner */}
        {error && errorMessages[error] && (
          <div
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "8px",
              backgroundColor: "var(--coral-bg)",
              border: "1px solid var(--coral)",
              color: "var(--coral-2)",
              fontSize: "0.85rem",
              marginBottom: "1.5rem",
            }}
          >
            {errorMessages[error]}
          </div>
        )}

        {/* Magic-link form */}
        {state === "sent" ? (
          <div
            style={{
              padding: "1.5rem",
              borderRadius: "8px",
              backgroundColor: "var(--green-bg)",
              border: "1px solid var(--green)",
              color: "var(--green)",
              fontSize: "0.9rem",
              textAlign: "center",
              marginBottom: "1.5rem",
            }}
          >
            Check your email — we sent you a sign-in link.
          </div>
        ) : (
          <form onSubmit={handleEmailSubmit} style={{ marginBottom: "1.5rem" }}>
            <label
              style={{
                display: "block",
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "var(--text-dim)",
                marginBottom: "0.5rem",
              }}
            >
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              style={{
                width: "100%",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                border: "1px solid var(--border)",
                backgroundColor: "var(--bg)",
                color: "var(--text)",
                fontFamily: "var(--font-sans)",
                fontSize: "0.95rem",
                outline: "none",
                boxSizing: "border-box",
                marginBottom: "0.75rem",
              }}
            />
            <button
              type="submit"
              disabled={state === "loading"}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "8px",
                border: "none",
                backgroundColor: "var(--gold)",
                color: "var(--bg)",
                fontFamily: "var(--font-mono)",
                fontSize: "0.8rem",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                fontWeight: 600,
                cursor: state === "loading" ? "wait" : "pointer",
                opacity: state === "loading" ? 0.7 : 1,
              }}
            >
              {state === "loading" ? "Sending…" : "Send sign-in link"}
            </button>
          </form>
        )}

        {/* Divider */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ flex: 1, height: "1px", backgroundColor: "var(--border)" }} />
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.7rem",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "var(--text-dim)",
            }}
          >
            or
          </span>
          <div style={{ flex: 1, height: "1px", backgroundColor: "var(--border)" }} />
        </div>

        {/* Lichess OAuth button */}
        <button
          onClick={handleLichessSignIn}
          style={{
            width: "100%",
            padding: "0.75rem",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            backgroundColor: "transparent",
            color: "var(--text)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.8rem",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
          }}
        >
          {/* Simple Lichess knight icon via text */}
          <span style={{ fontSize: "1.1rem", lineHeight: 1 }}>♞</span>
          Sign in with Lichess
        </button>

        {/* Guest note */}
        <p
          style={{
            fontSize: "0.78rem",
            color: "var(--text-dim)",
            textAlign: "center",
            marginTop: "1.5rem",
            marginBottom: 0,
          }}
        >
          Or just start training —{" "}
          <a
            href="/train"
            style={{ color: "var(--gold)", textDecoration: "underline" }}
          >
            continue as guest
          </a>
          .
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
