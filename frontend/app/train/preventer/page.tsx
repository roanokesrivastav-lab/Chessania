"use client";

import { Suspense, type ReactNode } from "react";
import TrainerShell from "@/components/train/TrainerShell";
import type { PositionItem } from "@/lib/train";

/**
 * /train/preventer — defensive drills on the user's danger positions.
 * "Opponent just played X — what's the threat, and how do you meet it?"
 *
 * V2-S5: built on the shared TrainerShell. Uses the "danger" category,
 * shows the opponent's last move above the board, and uses softer
 * wrong-answer copy ("Missed it" instead of "Fail").
 */
function PreventerPageInner() {
  return (
    <TrainerShell
      trainer="preventer"
      category="danger"
      routePath="/train/preventer"
      title="Blunder Preventer"
      description="Opponent played a threat — find the best defensive move to meet it."
      emptyStateText="No danger positions yet. Run a fresh v1 analysis first to mine defensive positions, then come back."
      failCopy={{ label: "Missed it", hint: "Here's the idea — see the best line below. The threat was real; next time, pause before moving." }}
      renderPrompt={renderDangerPrompt}
    />
  );
}

/** Show the opponent's last move (when available) above the board. */
function renderDangerPrompt(position: PositionItem): ReactNode {
  if (position.opponent_move_san) {
    return (
      <>
        Opponent just played{" "}
        <strong style={{ color: "var(--coral)" }}>
          {position.opponent_move_san}
        </strong>{" "}
        — what&rsquo;s the threat, and how do you meet it?
      </>
    );
  }
  return (
    <>
      What&rsquo;s the threat here — and how do you meet it?
    </>
  );
}

export default function PreventerPage() {
  return (
    <Suspense fallback={null}>
      <PreventerPageInner />
    </Suspense>
  );
}
