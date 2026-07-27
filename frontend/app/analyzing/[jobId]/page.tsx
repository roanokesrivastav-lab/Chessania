"use client";

import { useParams } from "next/navigation";

export default function AnalyzingPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        Analyzing job {jobId}…
      </h1>
      <p className="text-foreground/70">
        The live progress screen is coming in the next session.
      </p>
    </main>
  );
}
