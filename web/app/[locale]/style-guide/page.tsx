import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { Badge } from "@/components/ui/badge";
import { Waveform } from "@/components/waveform";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { TokenSwatches } from "@/components/style-guide/token-swatches";
import { PrimitivesDemo } from "@/components/style-guide/primitives-demo";

// The living catalogue of Voxa's design system (VOXA_DESIGN_PLAN.md §11): every token and
// primitive in both themes and all three languages. A tool for building the app, not a page
// for the public: kept out of search (robots.ts disallows it too).
export const metadata: Metadata = { robots: { index: false, follow: false } };

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-ui-label uppercase text-muted-foreground">{title}</h2>
        {note && <p className="mt-1 text-ui-small text-muted-foreground">{note}</p>}
      </div>
      {children}
    </section>
  );
}

// The app's desktop scale (text-ui-*), with what each role is for.
const UI_SCALE = [
  ["text-ui-display", "28 / 34 · 600", "Splash, empty states"],
  ["text-ui-title", "20 / 28 · 600", "Page title"],
  ["text-ui-section", "15 / 22 · 600", "Panel and section titles"],
  ["text-ui-body", "14 / 20", "Most of the interface"],
  ["text-ui-editor", "15 / 24", "Translation lines being edited"],
  ["text-ui-small", "13 / 18", "Hints, meta"],
  ["text-ui-label", "11 / 16 · 500 · uppercase", "Section labels, sparingly"],
] as const;

const MOTION = [
  ["--dur-1", "100 ms", "Hover, color"],
  ["--dur-2", "160 ms", "Menus, tooltips, toasts"],
  ["--dur-3", "220 ms", "Panels, dialogs, the sidebar"],
  ["--dur-4", "320 ms", "Page-level, rare; the splash"],
] as const;

export default async function StyleGuide({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <main id="main-content" className="mx-auto w-full max-w-6xl px-6 py-12">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Waveform bars={7} className="h-6" />
          <h1 className="text-ui-title">Voxa</h1>
          <Badge variant="brand">Design system · S0</Badge>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <div className="space-y-16">
        <Section
          title="Color tokens"
          note="Read live from the theme. Ratios are WCAG contrast on surface-1 and surface-3; npm run check:contrast holds every text pair to 4.5:1."
        >
          <TokenSwatches />
        </Section>

        <Section title="Type — the app's desktop scale" note="Inter; numbers and time codes in JetBrains Mono, tabular.">
          <div className="divide-y divide-border rounded-lg border border-border bg-surface-1">
            {UI_SCALE.map(([cls, spec, use]) => (
              <div key={cls} className="grid gap-1 px-5 py-3 sm:grid-cols-[1fr_auto] sm:items-baseline">
                <p className={`${cls} ${cls === "text-ui-label" ? "uppercase" : ""}`}>
                  Ən uzun sətir · Şu satır · Every line in its place
                </p>
                <p className="font-mono text-ui-mono text-muted-foreground">
                  {cls} — {spec} — {use}
                </p>
              </div>
            ))}
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 px-5 py-3">
              <span className="font-mono text-ui-mono tabular">00:05.3 → 00:09.7</span>
              <span className="font-mono text-ui-mono tabular text-muted-foreground">72 / 74</span>
              <span className="font-mono text-ui-mono text-muted-foreground">text-ui-mono — 12 / 18</span>
            </div>
          </div>
        </Section>

        <Section title="Type — the landing's scale" note="Kept for the site: larger, for reading.">
          <div className="space-y-3">
            <p className="type-h1">H1 — Anchored to the source</p>
            <p className="type-h3">H3 — Card title</p>
            <p className="type-body max-w-2xl text-muted-foreground">
              Body — 16 px with a 1.6 line height, for reading rather than working.
            </p>
          </div>
        </Section>

        <Section
          title="Motion"
          note="Only opacity and transform move; nothing bounces. Under prefers-reduced-motion everything is instant."
        >
          <div className="grid gap-3 sm:grid-cols-4">
            {MOTION.map(([token, ms, use]) => (
              <div key={token} className="rounded-md border border-border bg-surface-1 p-3">
                <p className="font-mono text-ui-mono text-foreground">{token}</p>
                <p className="text-ui-body">{ms}</p>
                <p className="text-ui-small text-muted-foreground">{use}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Primitives" note="Radix underneath (focus, keyboard, screen readers); Voxa's tokens on top.">
          <PrimitivesDemo />
        </Section>

        <Section title="Patterns">
          <div className="grid gap-5 md:grid-cols-2">
            <TerminalBlock command="voxa talk.mp4 --target_lang tr --preview" />
            <div className="flex items-center justify-center rounded-lg border border-border bg-surface-1 py-10">
              <Waveform bars={16} className="h-12" />
            </div>
          </div>
        </Section>
      </div>
    </main>
  );
}
