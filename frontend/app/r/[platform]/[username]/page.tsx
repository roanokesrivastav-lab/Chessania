"use client";

import { useParams } from "next/navigation";

export default function ReportPage() {
  const { platform, username } = useParams<{
    platform: string;
    username: string;
  }>();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        Your report for {username} is coming in the next session.
      </h1>
      <p className="text-foreground/70">Platform: {platform}</p>
    </main>
  );
}
