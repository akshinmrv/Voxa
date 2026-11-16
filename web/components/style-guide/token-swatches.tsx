"use client";

import { useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";

/** The <html> classes, which say the theme: the swatches read the tokens again when it flips. */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}
const themeClass = () => document.documentElement.className;
const noTheme = () => "";

const luminance = (hex: string) => {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const HEX = /^#[0-9a-f]{6}$/i;
/** The build's minifier writes #ffffff as #fff; the contrast math wants all six digits. */
const longHex = (value: string) =>
  /^#[0-9a-f]{3}$/i.test(value) ? `#${[...value.slice(1)].map((c) => c + c).join("")}` : value;

type Group = { title: string; tokens: string[]; text?: boolean };

const GROUPS: Group[] = [
  {
    title: "Surfaces",
    tokens: ["background", "surface-0", "surface-1", "surface-2", "surface-3", "border", "border-strong"],
  },
  { title: "Text (ratio on surface-1 · surface-3)", tokens: ["foreground", "muted-foreground", "fg-subtle"], text: true },
  {
    title: "Brand & semantic (ratio on surface-1 · surface-3)",
    tokens: ["primary", "success", "warning", "danger", "destructive", "info"],
    text: true,
  },
];

export function TokenSwatches() {
  const t = useTranslations("App.review");
  const theme = useSyncExternalStore(subscribe, themeClass, noTheme);
  const read = (name: string) =>
    theme === ""
      ? ""
      : longHex(getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim());
  const s1 = read("surface-1");
  const s3 = read("surface-3");
  const ratios = (value: string) =>
    HEX.test(value) && HEX.test(s1) && HEX.test(s3)
      ? `${contrast(value, s1).toFixed(2)} · ${contrast(value, s3).toFixed(2)}`
      : "";
  // `destructive` is a fill, never text: what counts is the text on it.
  const onFill = (name: string, value: string) => {
    const ink = read(`${name}-foreground`);
    return HEX.test(value) && HEX.test(ink) ? `text on it ${contrast(ink, value).toFixed(2)}` : "";
  };

  return (
    <div className="space-y-8">
      {GROUPS.map((group) => (
        <div key={group.title} className="space-y-3">
          <h3 className="text-ui-section">{group.title}</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            {group.tokens.map((name) => {
              const value = read(name);
              return (
                <div key={name} className="space-y-1.5">
                  <div
                    className="h-14 rounded-md border border-border"
                    style={{ background: `var(--${name})` }}
                  />
                  <p className="font-mono text-ui-mono text-foreground">{name}</p>
                  <p className="font-mono text-ui-mono text-muted-foreground">
                    {value || "—"}
                    {group.text && (
                      <span className="block">
                        {name === "destructive" ? onFill(name, value) : ratios(value)}
                      </span>
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div className="space-y-3">
        <h3 className="text-ui-section">Speakers (always with their label)</h3>
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <span
              key={n}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-1 px-2.5 py-0.5 text-ui-small"
            >
              <span className="size-2 rounded-full" style={{ background: `var(--sp-${n})` }} />
              <span style={{ color: `var(--sp-${n})` }}>{t("speaker", { n })}</span>
              <span className="font-mono text-ui-mono text-fg-subtle">{ratios(read(`sp-${n}`)).split(" · ")[0]}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
