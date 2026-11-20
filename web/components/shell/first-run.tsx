"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { AlertTriangle, ArrowRight, CheckCircle2, Clapperboard, XCircle } from "lucide-react";
import { getDoctor } from "@/lib/api";
import type { DoctorCheck } from "@/lib/types";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { SegmentedControl } from "@/components/ui/segmented";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ThemeChoice } from "./theme-choice";
import { cn } from "@/lib/utils";

/** Set once the welcome is through or skipped. The window's storage lasts; a browser's too. */
export const WELCOMED_KEY = "voxa.welcomed";
/** Settings › About asks for the welcome again with this event. */
export const WELCOME_EVENT = "voxa:welcome";

const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  az: "Azərbaycanca",
  tr: "Türkçe",
};

function welcomed(): boolean {
  try {
    return window.localStorage.getItem(WELCOMED_KEY) === "1";
  } catch {
    return true; // no storage: don't ask on every page
  }
}

/** The checks a first look needs: can it run, will it be quick, can it speak. */
const FIRST_CHECKS: [string, string][] = [
  ["Required", "FFmpeg"],
  ["Speed", "GPU"],
  ["Speech", "Edge"],
];

const ICON = {
  ok: { icon: CheckCircle2, tone: "text-success" },
  warn: { icon: AlertTriangle, tone: "text-warning" },
  fail: { icon: XCircle, tone: "text-danger" },
  off: { icon: AlertTriangle, tone: "text-fg-subtle" },
} as const;

function SystemStep() {
  const t = useTranslations("App.welcome");
  const doctor = useQuery({ queryKey: ["doctor", false], queryFn: () => getDoctor(false) });
  if (doctor.isPending)
    return <p className="text-ui-body text-muted-foreground">{t("checking")}</p>;
  if (!doctor.data) return <p className="text-ui-body text-muted-foreground">{t("noCheck")}</p>;
  const rows = FIRST_CHECKS.map(([section, name]) =>
    doctor.data.checks.find((c) => c.section === section && c.name === name),
  ).filter(Boolean) as DoctorCheck[];
  return (
    <div className="space-y-3">
      <p
        className={cn(
          "text-ui-body font-medium",
          doctor.data.ready ? "text-success" : "text-danger",
        )}
      >
        {doctor.data.ready ? t("ready") : t("notReady")}
      </p>
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface-1">
        {rows.map((c) => {
          const { icon: Icon, tone } = ICON[c.status];
          return (
            <li key={c.name} className="space-y-1.5 px-3 py-2.5">
              <p className="flex items-start gap-2.5 text-ui-body">
                <Icon className={cn("mt-0.5 size-4 shrink-0", tone)} aria-hidden />
                <span className="font-medium">{c.name}</span>
                <span className="min-w-0 text-muted-foreground [overflow-wrap:anywhere]">
                  {c.detail}
                </span>
              </p>
              {c.status === "fail" && c.fix && (
                <div className="ml-6 flex items-start gap-1 rounded-sm border border-border bg-surface-2 py-1 pl-2.5 pr-1">
                  <code className="min-w-0 flex-1 py-0.5 font-mono text-ui-mono [overflow-wrap:anywhere]">
                    {c.fix}
                  </code>
                  <CopyButton text={c.fix} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <p className="text-ui-small text-muted-foreground">{t("systemMore")}</p>
    </div>
  );
}

/**
 * The first time the console opens (VOXA_DESIGN_PLAN.md §8.10): a language and a theme, what
 * this machine can do, and the shortest way to a first dub, a preview of 20 seconds. Each step
 * can be skipped; Settings › About shows it again.
 */
export function FirstRun() {
  const t = useTranslations("App.welcome");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    // After the page is drawn, so a first frame never waits on storage.
    const id = setTimeout(() => setOpen(!welcomed()), 0);
    const again = () => {
      setStep(0);
      setOpen(true);
    };
    window.addEventListener(WELCOME_EVENT, again);
    return () => {
      clearTimeout(id);
      window.removeEventListener(WELCOME_EVENT, again);
    };
  }, []);

  function done() {
    try {
      window.localStorage.setItem(WELCOMED_KEY, "1");
    } catch {
      /* asked again next time */
    }
    setOpen(false);
  }

  const steps = [
    {
      title: t("title"),
      body: (
        <div className="space-y-5">
          <p className="text-ui-body text-muted-foreground">{t("intro")}</p>
          <div className="space-y-2">
            <p className="text-ui-body font-medium">{t("language")}</p>
            <SegmentedControl
              aria-label={t("language")}
              value={locale}
              onValueChange={(next) => router.replace(pathname, { locale: next })}
              items={routing.locales.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] ?? l }))}
            />
          </div>
          <div className="space-y-2">
            <p className="text-ui-body font-medium">{t("theme")}</p>
            <ThemeChoice />
          </div>
        </div>
      ),
    },
    { title: t("systemTitle"), body: <SystemStep /> },
    {
      title: t("dubTitle"),
      body: (
        <div className="space-y-3">
          <p className="text-ui-body text-muted-foreground">{t("dubIntro")}</p>
          <ol className="list-decimal space-y-1.5 pl-5 text-ui-body marker:text-fg-subtle">
            <li>{t("dub1")}</li>
            <li>{t("dub2")}</li>
            <li>{t("dub3")}</li>
          </ol>
        </div>
      ),
    },
  ];
  const last = step === steps.length - 1;

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : done())}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <p className="text-ui-label uppercase text-muted-foreground">
            {t("step", { n: step + 1, total: steps.length })}
          </p>
          <DialogTitle>{steps[step].title}</DialogTitle>
          <DialogDescription className="sr-only">{t("intro")}</DialogDescription>
        </DialogHeader>
        <div className="min-h-44">{steps[step].body}</div>
        <DialogFooter className="items-center sm:justify-between">
          <Button variant="ghost" size="sm" onClick={done}>
            {t("skip")}
          </Button>
          <span className="flex gap-2">
            {step > 0 && (
              <Button variant="secondary" size="sm" onClick={() => setStep(step - 1)}>
                {t("back")}
              </Button>
            )}
            {last ? (
              <Button asChild size="sm">
                <Link href="/app" onClick={done}>
                  <Clapperboard /> {t("start")}
                </Link>
              </Button>
            ) : (
              <Button size="sm" onClick={() => setStep(step + 1)}>
                {t("next")} <ArrowRight />
              </Button>
            )}
          </span>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
