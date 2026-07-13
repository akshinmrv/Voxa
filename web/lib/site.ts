/**
 * Site-wide constants for SEO, structured data, and the author/brand section.
 * The public URL is configurable — set NEXT_PUBLIC_SITE_URL to the real domain
 * before deploying (the default below is a placeholder).
 */
/**
 * Public site URL for SEO. Precedence:
 *  1. NEXT_PUBLIC_SITE_URL (set it explicitly for a custom domain), else
 *  2. Vercel's stable production domain (auto-injected at build), else
 *  3. a placeholder.
 */
function resolveSiteUrl(): string {
  if (process.env.NEXT_PUBLIC_SITE_URL) return process.env.NEXT_PUBLIC_SITE_URL;
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL)
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  return "https://voxa.servoogle.com";
}

export const SITE = {
  name: "Voxa",
  url: resolveSiteUrl().replace(/\/$/, ""),
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
