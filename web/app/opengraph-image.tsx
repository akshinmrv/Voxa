import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Voxa — Dub any video into another language and keep it in sync";

// Branded social-share card (auto-wired into OpenGraph + Twitter via metadataBase).
export default function OpengraphImage() {
  const bars = [0.35, 0.7, 1, 0.55, 0.85, 0.4, 0.95, 0.6, 0.75, 0.45, 0.9, 0.5];
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0a0a0b",
          padding: 72,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, height: 80 }}>
          {bars.map((h, i) => (
            <div
              key={i}
              style={{
                width: 12,
                height: `${h * 100}%`,
                background: "#38bdf8",
                borderRadius: 6,
              }}
            />
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 128, fontWeight: 700, color: "#fafafa", letterSpacing: -4 }}>
            Voxa
          </div>
          <div style={{ fontSize: 40, color: "#a1a1aa", maxWidth: 900 }}>
            Dub any video into another language — and keep it in sync.
          </div>
        </div>

        <div style={{ display: "flex", fontSize: 28, color: "#71717a", gap: 16 }}>
          <span style={{ color: "#38bdf8" }}>Open source · MIT</span>
          <span>·</span>
          <span>Built by Servoogle</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
