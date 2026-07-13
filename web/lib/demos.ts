export type DemoClip = { code: string; src: string };

/**
 * Shipped demo clips (served from web/public/demo). One source video dubbed by
 * Voxa into several languages. Empty → the Demo section shows a placeholder.
 */
export const DEMOS: DemoClip[] = [
  { code: "original", src: "/demo/original.mp4" },
  { code: "tr", src: "/demo/dub_tr.mp4" },
  { code: "az", src: "/demo/dub_az.mp4" },
  { code: "fr", src: "/demo/dub_fr.mp4" },
];

/** A dubbed clip (not the original) used for VideoObject structured data. */
export const PRIMARY_DEMO = DEMOS.find((d) => d.code !== "original") ?? null;
