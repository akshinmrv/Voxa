// Build the operator console as static files and copy them into the Python package
// (voxa_ui/static), where `voxa serve` finds and serves them. Run it before building
// the wheel:  npm run build:console
//
// The console calls the API on the same origin, so NEXT_PUBLIC_VOXA_API is empty. The
// landing page's demo videos, the site-verification files and the installers the site
// hands out stay out of the package, as do the pages the console never shows: the site's
// landing page and the style guide (about 2 MB over three languages). `voxa serve` sends a
// bare /<locale>/ to the console.
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, rmSync } from "node:fs";
import { basename, dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const web = dirname(dirname(fileURLToPath(import.meta.url)));
const out = join(web, "out");
const target = join(web, "..", "voxa_ui", "static");

const SKIP_DIRS = new Set(["demo", "tts-samples"]);
const SKIP_FILE = /^(BingSiteAuth\.xml|google[0-9a-f]+\.html|install\.(sh|ps1))$/;
const LOCALES = new Set(["en", "az", "tr"]);

/** The site's own pages under a locale: its landing page (and that page's payloads), the
 *  style guide. The console's pages, under <locale>/app/, carry their own payloads. */
function siteOnly(parts) {
  if (!LOCALES.has(parts[0]) || parts.length < 2) return false;
  const [, page] = parts;
  if (page === "style-guide" || page === "__next.$d$locale") return true;
  return (
    parts.length === 2 &&
    (page === "index.html" || page === "index.txt" || page.startsWith("__next."))
  );
}

const build = spawnSync(
  process.execPath,
  [join(web, "node_modules", "next", "dist", "bin", "next"), "build"],
  {
    cwd: web,
    stdio: "inherit",
    env: {
      ...process.env,
      VOXA_UI_EXPORT: "1",
      NEXT_PUBLIC_VOXA_API: "",
      NEXT_PUBLIC_TARGET: "console",
    },
  },
);
if (build.status !== 0) process.exit(build.status ?? 1);

rmSync(target, { recursive: true, force: true });
cpSync(out, target, {
  recursive: true,
  filter: (src) => {
    const rel = relative(out, src);
    if (!rel) return true;
    const parts = rel.split(sep);
    if (SKIP_DIRS.has(parts[0]) || siteOnly(parts)) return false;
    return !SKIP_FILE.test(basename(src));
  },
});

if (!existsSync(join(target, "en", "app", "index.html"))) {
  console.error(`build-console: ${target} has no en/app/index.html`);
  process.exit(1);
}
console.log(`build-console: console copied to ${target}`);
