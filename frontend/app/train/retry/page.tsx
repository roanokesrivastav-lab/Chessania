"use client";

import { Suspense } from "react";
import TrainerShell from "@/components/train/TrainerShell";

/**
 * /train/retry — replays the user's own blunder positions with two-tier grading.
 *
 * V2-S5: extracted into the shared TrainerShell; this is now a thin wrapper
 * that only configures the shell with retry-specific props. Behavior is unchanged
 * from V2-S4.
 */
function RetryPageInner() {
  return (
    <TrainerShell
      trainer="retry"
      category="blunder"
      routePath="/train/retry"
      title="Retry Your Mistakes"
      description="Practice positions where you blundered — from your own games."
    />
  );
}

export default function RetryPage() {
  return (
    <Suspense fallback={null}>
      <RetryPageInner />
    </Suspense>
  );
}
