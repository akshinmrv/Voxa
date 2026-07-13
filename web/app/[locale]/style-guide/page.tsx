import { setRequestLocale } from "next-intl/server";
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
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

export default async function StyleGuide({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-16">
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

      <div className="space-y-20">
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

        <Section title="Typography">
          <div className="space-y-4">
            <p className="type-display">Display — Inter 700</p>
            <p className="type-h1">H1 — Section heading</p>
            <p className="type-h2">H2 — Subheading</p>
            <p className="type-h3">H3 — Card title</p>
            <p className="type-body max-w-2xl">
              Body — the base reading size is 16px with a 1.6 line height.
            </p>
            <p className="type-small text-muted-foreground">Small — 14px.</p>
            <p className="type-label text-muted-foreground">Label — uppercase</p>
            <p className="type-code text-muted-foreground">
              Code — JetBrains Mono · WER{" "}
              <span className="tabular text-foreground">0.02</span>
            </p>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Get started</Button>
            <Button variant="secondary">View on GitHub</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Delete</Button>
            <Button variant="link">Docs</Button>
          </div>
        </Section>

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
          </div>
        </Section>

        <Section title="Terminal & waveform">
          <div className="grid gap-6 md:grid-cols-2">
            <TerminalBlock command="voxa talk.mp4 --target_lang ru" />
            <Card className="flex items-center justify-center py-10">
              <Waveform bars={16} className="h-12" />
            </Card>
          </div>
        </Section>

        <Section title="Cards">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Anchored placement</CardTitle>
                <CardDescription>Drift stays at zero.</CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant="success">
                  <CheckCircle2 /> MIT licensed
                </Badge>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Four TTS engines</CardTitle>
                <CardDescription>Edge, OpenAI, Piper, XTTS.</CardDescription>
              </CardHeader>
            </Card>
          </div>
        </Section>
      </div>
    </main>
  );
}
