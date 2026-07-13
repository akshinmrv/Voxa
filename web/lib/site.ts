/**
 * Site-wide constants for SEO, structured data, and the author/brand section.
 * The public URL is configurable — set NEXT_PUBLIC_SITE_URL to the real domain
 * before deploying (the default below is a placeholder).
 */
export const SITE = {
  name: "Voxa",
  url: (process.env.NEXT_PUBLIC_SITE_URL ?? "https://voxa.servoogle.com").replace(
    /\/$/,
    "",
  ),
  repo: "https://github.com/akshinmrv/Voxa",
  locales: ["en", "az", "tr"] as const,
  defaultLocale: "en" as const,

  author: {
    name: "Akshin Miranov",
    github: "https://github.com/akshinmrv",
  },

  org: {
    name: "Servoogle",
    // TODO(brand): replace with Servoogle's official site/logo/mission when available.
    url: "https://github.com/akshinmrv",
  },

  // Consistent entity links (sameAs) for the knowledge graph / GEO.
  sameAs: [
    "https://github.com/akshinmrv/Voxa",
    "https://github.com/akshinmrv",
  ],
} as const;

/** Absolute URL for a locale's landing page. */
export const localeUrl = (locale: string) => `${SITE.url}/${locale}`;

/**
 * Build target. On a public deploy (NEXT_PUBLIC_TARGET=public) the operator app
 * is replaced by a "run locally" notice — dubbing only ever runs on the user's
 * own machine. The default (local) ships the full app.
 */
export const IS_PUBLIC = process.env.NEXT_PUBLIC_TARGET === "public";
