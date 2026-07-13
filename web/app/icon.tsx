import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

// Waveform glyph — the Voxa brand mark (no text, so no font is needed).
export default function Icon() {
  const bars = [0.4, 0.75, 1, 0.55, 0.35];
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 5,
          background: "#0a0a0b",
        }}
      >
        {bars.map((h, i) => (
          <div
            key={i}
            style={{
              width: 7,
              height: `${h * 62}%`,
              background: "#38bdf8",
              borderRadius: 4,
            }}
          />
        ))}
      </div>
    ),
    { ...size },
  );
}
