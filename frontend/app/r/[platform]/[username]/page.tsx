import type { Metadata } from "next";
import { getReport, ApiError } from "@/lib/api";
import type { Platform } from "@/lib/types";
import AnalyzeForm from "@/components/AnalyzeForm";
import ReportHeader from "@/components/report/ReportHeader";
import StrengthCard from "@/components/report/StrengthCard";
import CategoryDashboard from "@/components/report/CategoryDashboard";
import OpeningRecCards from "@/components/report/OpeningRecCards";
import ProgressStrip from "@/components/report/ProgressStrip";
import ReportFooter from "@/components/report/ReportFooter";

export const dynamic = "force-dynamic";

interface PageParams {
  params: Promise<{ platform: string; username: string }>;
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { platform, username } = await params;
  return {
    title: username,
    description: `Free coaching report for ${username} on ${platform} — from Stockfish analysis of their last games.`,
    openGraph: {
      title: `${username} · Chessania report`,
      description: `Free coaching report for ${username} on ${platform} — from Stockfish analysis of their last games.`,
      url: `/r/${platform}/${username}`,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
    },
  };
}

function isPlatform(value: string): value is Platform {
  return value === "chesscom" || value === "lichess";
}

export default async function ReportPage({ params }: PageParams) {
  const { platform: rawPlatform, username } = await params;

  if (!isPlatform(rawPlatform)) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12 text-center">
        <h1 className="text-2xl font-bold">Unknown platform</h1>
        <p className="mt-2 text-foreground/70">Use chesscom or lichess.</p>
      </main>
    );
  }

  let report;
  try {
    report = await getReport(rawPlatform, username);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return (
        <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12">
          <div className="w-full max-w-md space-y-6 text-center">
            <h1 className="text-2xl font-bold">No report yet</h1>
            <p className="text-foreground/70">
              No report for {username} on {rawPlatform} — want one?
            </p>
            <AnalyzeForm initialPlatform={rawPlatform} />
          </div>
        </main>
      );
    }

    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12 text-center">
        <h1 className="text-2xl font-bold">Couldn&apos;t load this report</h1>
        <p className="mt-2 text-foreground/70">Try again in a minute.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl space-y-8">
        <ReportHeader
          summary={report.player_summary}
          playstyle={report.playstyle}
        />
        <StrengthCard strengths={report.strengths} />
        <CategoryDashboard report={report} />
        <OpeningRecCards recs={report.opening_recs} />
        <ProgressStrip progress={report.progress} />
        <ReportFooter
          platform={report.player_summary.platform}
          username={report.player_summary.username}
          games_analyzed={report.player_summary.games_analyzed}
          engine_depth={report.engine_depth}
          generated_at={report.generated_at}
        />
      </div>
    </main>
  );
}
