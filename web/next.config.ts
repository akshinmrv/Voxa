import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  // Pin the workspace root to this folder. Without it, Turbopack walks up to find
  // a lockfile and a stray one in a parent dir (e.g. ~/package-lock.json) hijacks
  // module resolution, which produces broken middleware bundles ("adapterFn is
  // not a function") and 404s.
  turbopack: {
    root: __dirname,
  },
};

export default withNextIntl(nextConfig);
