// Check that the color tokens in app/globals.css meet WCAG 2.2 AA in both themes:
// 4.5:1 for text, 3:1 for what isn't text but has to be seen (focus rings, control
// outlines). Fails the build when a pair falls short, so a token can't drift under it.
//   npm run check:contrast
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = dirname(dirname(fileURLToPath(import.meta.url)));
const css = readFileSync(join(web, "app", "globals.css"), "utf8");

/** The `--name: #hex` declarations of the first block that opens with `selector {`. */
function tokens(selector) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no "${selector} {" block in globals.css`);
  const body = css.slice(start, css.indexOf("\n}", start));
  const out = {};
  for (const [, name, hex] of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[name] = hex.toLowerCase();
  }
  return out;
}

const dark = tokens(":root");
const themes = { dark, light: { ...dark, ...tokens(".light") } };

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const channel = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = (hex) => {
  const [r, g, b] = rgb(hex).map(channel);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
/** `color` at `alpha` over `under`, as a badge's tinted background is drawn. */
const over = (color, alpha, under) => {
  const [c, u] = [rgb(color), rgb(under)];
  const mixed = c.map((v, i) => Math.round((v * alpha + u[i] * (1 - alpha)) * 255));
  return `#${mixed.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
};

const SURFACES = ["background", "surface-0", "surface-1", "surface-2", "surface-3"];
const TEXT = 4.5;
const SEEN = 3;

/** [foreground, background or [tint, alpha, under], minimum, what it is] */
function checks(t) {
  const list = [];
  for (const fg of ["foreground", "muted-foreground", "fg-subtle"]) {
    for (const bg of SURFACES) list.push([fg, bg, TEXT, "text"]);
  }
  for (const fg of ["primary", "danger"]) {
    for (const bg of ["background", "surface-1", "surface-2"]) list.push([fg, bg, TEXT, "text"]);
  }
  list.push(["primary-foreground", "primary", TEXT, "button"]);
  list.push(["destructive-foreground", "destructive", TEXT, "button"]);
  list.push(["success-foreground", "success", TEXT, "fill"]);
  list.push(["warning-foreground", "warning", TEXT, "fill"]);
  // Badges: the color as text on a 15% tint of itself.
  for (const c of ["brand", "success", "warning", "danger"]) {
    for (const under of ["background", "surface-1"]) list.push([c, [c, 0.15, under], TEXT, "badge"]);
  }
  for (let n = 1; n <= 6; n++) {
    for (const bg of ["surface-1", "surface-2"]) list.push([`sp-${n}`, bg, TEXT, "speaker"]);
  }
  for (const bg of ["background", "surface-1", "surface-2"]) {
    list.push(["ring", bg, SEEN, "focus ring"]);
    list.push(["border-strong", bg, SEEN, "control outline"]);
  }
  return list.map(([fg, bg, min, what]) => {
    const back = Array.isArray(bg) ? over(t[bg[0]], bg[1], t[bg[2]]) : t[bg];
    const label = Array.isArray(bg) ? `${bg[0]} ${bg[1] * 100}% on ${bg[2]}` : bg;
    if (!t[fg] || !back) throw new Error(`missing token for ${fg} on ${label}`);
    return { fg, bg: label, min, what, value: ratio(t[fg], back) };
  });
}

let failed = 0;
for (const [name, t] of Object.entries(themes)) {
  const results = checks(t);
  const bad = results.filter((r) => r.value < r.min);
  failed += bad.length;
  const lowest = results.reduce((a, b) => (b.value - b.min < a.value - a.min ? b : a));
  console.log(
    `${name}: ${results.length - bad.length}/${results.length} pass; closest: ` +
      `${lowest.fg} on ${lowest.bg} ${lowest.value.toFixed(2)}:1 (needs ${lowest.min})`,
  );
  for (const r of bad) {
    console.log(`  ✗ ${r.fg} on ${r.bg}: ${r.value.toFixed(2)}:1, needs ${r.min}:1 (${r.what})`);
  }
}
process.exit(failed ? 1 : 0);
