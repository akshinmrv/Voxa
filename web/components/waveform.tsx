import { cn } from "@/lib/utils";

// Deterministic bar heights (avoids SSR/client hydration mismatch).
const HEIGHTS = [0.4, 0.7, 1, 0.55, 0.85, 0.35, 0.95, 0.6, 0.75, 0.45, 0.9, 0.5];

/**
 * Waveform motif — Voxa's brand signature (DESIGN_SYSTEM.md §7.2, §16).
 * Purely decorative, so it's hidden from assistive tech. Bars animate under
 * `animated`, and hold still under prefers-reduced-motion (handled in globals.css).
 */
export function Waveform({
  bars = 12,
  animated = true,
  className,
}: {
  bars?: number;
  animated?: boolean;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn("flex h-8 items-center gap-1", className)}
    >
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-full bg-brand",
            animated && "voxa-wave-bar",
          )}
          style={{
            height: `${HEIGHTS[i % HEIGHTS.length] * 100}%`,
            animationDelay: `${(i % HEIGHTS.length) * 90}ms`,
          }}
        />
      ))}
    </div>
  );
}
