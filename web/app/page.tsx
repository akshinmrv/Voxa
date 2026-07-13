import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Waveform } from "@/components/waveform";
import { ThemeToggle } from "@/components/theme-toggle";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { CheckCircle2, AlertTriangle, XCircle, Info, Sparkles } from "lucide-react";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-6">
      <h2 className="type-label text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

function Swatch({ name, className }: { name: string; className: string }) {
  return (
    <div className="space-y-2">
      <div className={`h-16 rounded-md border border-border ${className}`} />
      <p className="type-code text-xs text-muted-foreground">{name}</p>
    </div>
  );
}

export default function StyleGuide() {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-16">
      {/* Header */}
      <header className="mb-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Waveform bars={7} className="h-6" />
          <span className="text-xl font-semibold tracking-tight">Voxa</span>
          <Badge variant="brand">
            <Sparkles /> Design System · D0
          </Badge>
        </div>
        <ThemeToggle />
      </header>

      <div className="mb-16 space-y-4">
        <h1 className="type-display max-w-3xl text-balance">
          Dub any video into another language — and keep it in sync.
        </h1>
        <p className="type-body max-w-2xl text-muted-foreground">
          Bu səhifə Voxa dizayn sisteminin təməlidir (D0): rəng token-ləri,
          typography, primitivlər və brend waveform motivi. Dark və light
          temaların hər ikisi işləyir — yuxarı sağdakı düymə ilə yoxlayın.
        </p>
      </div>

      <div className="space-y-20">
        {/* Colors */}
        <Section title="Color tokens">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Swatch name="background" className="bg-background" />
            <Swatch name="surface-1 / card" className="bg-surface-1" />
            <Swatch name="surface-2" className="bg-surface-2" />
            <Swatch name="border" className="bg-border" />
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Swatch name="primary / brand" className="bg-primary" />
            <Swatch name="success" className="bg-success" />
            <Swatch name="warning" className="bg-warning" />
            <Swatch name="danger" className="bg-danger" />
          </div>
        </Section>

        {/* Typography */}
        <Section title="Typography">
          <div className="space-y-4">
            <p className="type-display">Display — Inter 700</p>
            <p className="type-h1">H1 — Section heading</p>
            <p className="type-h2">H2 — Subheading</p>
            <p className="type-h3">H3 — Card title</p>
            <p className="type-body max-w-2xl">
              Body — the base reading size is 16px with a 1.6 line height for
              comfortable long-form text. Line length is kept in the 60–75
              character range.
            </p>
            <p className="type-small text-muted-foreground">
              Small — secondary text, 14px.
            </p>
            <p className="type-label text-muted-foreground">
              Label — uppercase, tracked
            </p>
            <p className="type-code text-muted-foreground">
              Code — JetBrains Mono · WER{" "}
              <span className="tabular text-foreground">0.02</span>
            </p>
          </div>
        </Section>

        {/* Buttons */}
        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Get started</Button>
            <Button variant="secondary">View on GitHub</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Delete</Button>
            <Button variant="link">Docs</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="default">Default</Button>
            <Button size="lg">Large</Button>
            <Button disabled>Disabled</Button>
          </div>
        </Section>

        {/* Badges */}
        <Section title="Status badges">
          <div className="flex flex-wrap gap-3">
            <Badge variant="neutral">Neutral</Badge>
            <Badge variant="brand">
              <Info /> Info
            </Badge>
            <Badge variant="success">
              <CheckCircle2 /> Done
            </Badge>
            <Badge variant="warning">
              <AlertTriangle /> Warning
            </Badge>
            <Badge variant="danger">
              <XCircle /> Failed
            </Badge>
            <Badge variant="outline">Outline</Badge>
          </div>
        </Section>

        {/* Cards */}
        <Section title="Cards">
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Anchored placement</CardTitle>
                <CardDescription>
                  Every clip is locked to the source timeline — the dub never
                  drifts behind the speaker.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Four TTS engines</CardTitle>
                <CardDescription>
                  Edge, OpenAI, Piper (offline), and XTTS (voice cloning).
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Self-hostable</CardTitle>
                <CardDescription>
                  Point any OpenAI-compatible TTS endpoint with
                  --openai-tts-base-url.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant="success">
                  <CheckCircle2 /> MIT licensed
                </Badge>
              </CardContent>
            </Card>
          </div>
        </Section>

        {/* Terminal + Waveform */}
        <Section title="Terminal & waveform">
          <div className="grid gap-6 md:grid-cols-2">
            <TerminalBlock command="voxa talk.mp4 --target_lang ru" />
            <Card className="flex items-center justify-center py-10">
              <Waveform bars={16} className="h-12" />
            </Card>
          </div>
        </Section>

        {/* Radius */}
        <Section title="Radius">
          <div className="flex flex-wrap gap-4">
            <div className="flex flex-col items-center gap-2">
              <div className="size-16 rounded-sm border border-border bg-surface-2" />
              <span className="type-code text-xs text-muted-foreground">
                sm · 6px
              </span>
            </div>
            <div className="flex flex-col items-center gap-2">
              <div className="size-16 rounded-md border border-border bg-surface-2" />
              <span className="type-code text-xs text-muted-foreground">
                md · 10px
              </span>
            </div>
            <div className="flex flex-col items-center gap-2">
              <div className="size-16 rounded-lg border border-border bg-surface-2" />
              <span className="type-code text-xs text-muted-foreground">
                lg · 16px
              </span>
            </div>
          </div>
        </Section>
      </div>

      <footer className="mt-24 border-t border-border pt-8">
        <p className="type-small text-fg-subtle">
          Voxa · MIT · Design System D0 — tokens, typography, primitives, brand
          waveform. Next: D1 (Landing).
        </p>
      </footer>
    </main>
  );
}
