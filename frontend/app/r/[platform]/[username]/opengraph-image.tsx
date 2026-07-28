import { ImageResponse } from "next/og";
import { getReport } from "@/lib/api";
import type { Report } from "@/lib/types";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Chessania coaching report";

interface Params {
  params: Promise<{ platform: string; username: string }>;
}

function isPlatform(value: string) {
  return value === "chesscom" || value === "lichess";
}

function fallbackCard(): ImageResponse {
  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #171717 0%, #2a2a2a 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#ffffff",
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          textAlign: "center",
          padding: "60px",
        }}
      >
        <div style={{ fontSize: 64, fontWeight: 800, marginBottom: 16 }}>
          Chessania
        </div>
        <div style={{ fontSize: 28, color: "#a3a3a3" }}>
          Free coaching report from your last 20 games — no signup.
        </div>
      </div>
    ),
    { ...size }
  );
}

function playerCard(report: Report): ImageResponse {
  const summary = report.player_summary;
  const rating = summary.rating ? `${summary.rating}` : "unrated";
  const platformLabel = summary.platform === "chesscom" ? "Chess.com" : "Lichess";

  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #171717 0%, #2a2a2a 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#ffffff",
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          textAlign: "center",
          padding: "60px",
        }}
      >
        <div style={{ fontSize: 56, fontWeight: 800, marginBottom: 16 }}>
          {summary.username}
        </div>
        <div
          style={{
            fontSize: 30,
            color: "#a3a3a3",
            marginBottom: 32,
          }}
        >
          {platformLabel} · {report.playstyle.label}
        </div>
        <div
          style={{
            display: "flex",
            gap: 48,
            fontSize: 24,
            color: "#d4d4d4",
          }}
        >
          <span>{rating} rating</span>
          <span>{summary.games_analyzed} games analyzed</span>
        </div>
      </div>
    ),
    { ...size }
  );
}

export default async function OpenGraphImage({ params }: Params) {
  try {
    const { platform: rawPlatform, username } = await params;

    if (!isPlatform(rawPlatform)) {
      return fallbackCard();
    }

    const report = await getReport(rawPlatform, username);
    return playerCard(report);
  } catch {
    return fallbackCard();
  }
}
