import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

// VOXA_UI_EXPORT=1 builds the operator console as static files (web/out) that
// `voxa serve` ships inside the Python package and serves itself — see
// scripts/build-console.mjs. Trailing slashes make every page a directory with an
// index.html, which a plain static file server resolves without rewrites.
const STATIC_EXPORT = process.env.VOXA_UI_EXPORT === "1";

const nextConfig: NextConfig = {
  ...(STATIC_EXPORT ? { output: "export" as const, trailingSlash: true } : {}),
  // Pin the workspace root to this folder. Without it, Turbopack walks up to find
  // a lockfile and a stray one in a parent dir (e.g. ~/package-lock.json) hijacks
  // module resolution, which produces broken middleware bundles ("adapterFn is
  // not a function") and 404s.
  turbopack: {
    root: __dirname,
  },
};

export default withNextIntl(nextConfig);
