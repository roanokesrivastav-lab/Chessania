import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Chessania — free chess coaching report";

export default function OpenGraphImage() {
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
        <div style={{ fontSize: 28, color: "#a3a3a3", maxWidth: 800 }}>
          Free coaching report from your last 20 games — no signup.
        </div>
      </div>
    ),
    { ...size }
  );
}
