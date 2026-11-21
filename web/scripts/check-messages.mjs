// The three languages' messages agree: the same keys, the same ICU arguments ({name},
// {count, plural, ...}) in each, no empty text, no key given twice, and the app's Azerbaijani
// and Turkish texts not left in English. Run: npm run check:messages (CI runs it with the web
// job).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const LOCALES = ["en", "az", "tr"];
const texts = Object.fromEntries(
  LOCALES.map((l) => [l, readFileSync(join(here, "..", "messages", `${l}.json`), "utf8")]),
);
const messages = Object.fromEntries(LOCALES.map((l) => [l, JSON.parse(texts[l])]));

/** Keys given twice in one object. JSON.parse keeps the last, so the first is never shown. */
function twice(text) {
  const found = [];
  const seen = [];
  const path = [];
  let key = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      let j = i + 1;
      while (text[j] !== '"') j += text[j] === "\\" ? 2 : 1;
      const name = JSON.parse(text.slice(i, j + 1));
      let k = j + 1;
      while (/\s/.test(text[k])) k++;
      if (text[k] === ":" && seen.length) {
        const here = seen[seen.length - 1];
        if (here.has(name)) found.push([...path.slice(1), name].join("."));
        here.add(name);
        key = name;
      }
      i = j;
    } else if (c === "{") {
      seen.push(new Set());
      path.push(key);
    } else if (c === "}") {
      seen.pop();
      path.pop();
    }
  }
  return found;
}

/** Every leaf, as "a.b.c" → value (arrays are leaves). */
function leaves(node, prefix = "", out = new Map()) {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) leaves(value, path, out);
    else out.set(path, value);
  }
  return out;
}

/** The ICU arguments a message takes: {name}, and the first word of {count, plural, ...}. */
function args(text) {
  if (typeof text !== "string") return [];
  const found = new Set();
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "{") {
      depth++;
      // an argument opens at depth 1, or inside a plural's branch at depth 3
      const m = /^\{\s*([A-Za-z_]\w*)\s*[,}]/.exec(text.slice(i));
      if (m && (depth === 1 || depth === 3)) found.add(m[1]);
    } else if (text[i] === "}") depth--;
  }
  return [...found].sort();
}

// Words and names that are the same in every language.
const SAME_EVERYWHERE = new Set([
  "Voxa",
  "Studio",
  "GitHub",
  "Edge",
  "Piper",
  "OpenAI",
  "Anthropic",
  "OpenRouter",
  "Google",
  "Ollama",
  "XTTS",
  "Whisper",
  "Python",
  "CPU",
  "GPU",
  "NVIDIA",
  "CUDA",
  "Apple",
  "Status",
  "Disk",
  "Performans",
  "terminal",
]);
// Texts meant to be the same in every language: a command to type.
const SAME_KEYS = new Set(["App.localOnly.serve", "App.localOnly.install"]);

/** What is left to translate once arguments and names are taken out. */
function words(text) {
  return text
    .replace(/\{[^{}]*\}/g, " ")
    .replace(/[A-Za-z][\w-]*/g, (w) => (SAME_EVERYWHERE.has(w) ? " " : w));
}

const problems = [];
for (const l of LOCALES) {
  for (const key of twice(texts[l]))
    problems.push(`${key}: given twice in ${l}; the first is never shown`);
}
const all = Object.fromEntries(LOCALES.map((l) => [l, leaves(messages[l])]));
const keys = new Set(LOCALES.flatMap((l) => [...all[l].keys()]));

for (const key of [...keys].sort()) {
  const values = Object.fromEntries(LOCALES.map((l) => [l, all[l].get(key)]));
  const missing = LOCALES.filter((l) => values[l] === undefined);
  if (missing.length) {
    problems.push(`${key}: missing in ${missing.join(", ")}`);
    continue;
  }
  for (const l of LOCALES) {
    if (values[l] === "" || (Array.isArray(values[l]) && !values[l].length))
      problems.push(`${key}: empty in ${l}`);
  }
  if (Array.isArray(values.en)) {
    for (const l of ["az", "tr"]) {
      if (values[l].length !== values.en.length)
        problems.push(`${key}: ${values.en.length} items in en, ${values[l].length} in ${l}`);
    }
    continue;
  }
  const want = args(values.en).join(",");
  for (const l of ["az", "tr"]) {
    const got = args(values[l]).join(",");
    if (got !== want) problems.push(`${key}: en takes {${want}}, ${l} takes {${got}}`);
  }
  // The app's own texts (not the marketing site's, which has its own review) left in English.
  if ((key.startsWith("App.") || key.startsWith("Common.")) && !SAME_KEYS.has(key)) {
    for (const l of ["az", "tr"]) {
      const text = values[l];
      if (typeof text === "string" && text === values.en && /[A-Za-z]{3}/.test(words(text)))
        problems.push(`${key}: ${l} is the English text: "${text}"`);
    }
  }
}

if (problems.length) {
  console.error(problems.join("\n"));
  console.error(`\n${problems.length} problem(s) in the messages`);
  process.exit(1);
}
console.log(`messages: ${keys.size} keys agree in ${LOCALES.join(", ")}`);
