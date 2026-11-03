// Build the operator console as static files and copy them into the Python package
// (voxa_ui/static), where `voxa serve` finds and serves them. Run it before building
// the wheel:  npm run build:console
//
// The console calls the API on the same origin, so NEXT_PUBLIC_VOXA_API is empty. The
// landing page's demo videos and site-verification files stay out of the package.
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, rmSync } from "node:fs";
import { basename, dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const web = dirname(dirname(fileURLToPath(import.meta.url)));
const out = join(web, "out");
const target = join(web, "..", "voxa_ui", "static");

const SKIP_DIRS = new Set(["demo", "tts-samples"]);
const SKIP_FILE = /^(BingSiteAuth\.xml|google[0-9a-f]+\.html)$/;

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
    if (SKIP_DIRS.has(rel.split(sep)[0])) return false;
    return !SKIP_FILE.test(basename(src));
  },
});

if (!existsSync(join(target, "en", "app", "index.html"))) {
  console.error(`build-console: ${target} has no en/app/index.html`);
  process.exit(1);
}
console.log(`build-console: console copied to ${target}`);
