"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowUpCircle, ChevronDown, Download, ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { useUpdateStatus } from "@/lib/use-update";
import { cn } from "@/lib/utils";

const DISMISSED_KEY = "voxa.update.dismissed";

function readDismissed(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(DISMISSED_KEY);
  } catch {
    return null; // storage blocked: the banner just comes back next time
  }
}

/**
 * A slim bar under the top bar when a newer Voxa is out: what it is, where its notes are,
 * and how this install gets it — the new VoxaSetup.exe for an install it made, otherwise the
 * one command that upgrades this kind of install. "Not now" hides it until the next release.
 */
export function UpdateBanner() {
  const t = useTranslations("App.update");
  const { data } = useUpdateStatus();
  // Read once on the first client render; the status arrives after hydration anyway.
  const [dismissed, setDismissed] = useState<string | null>(readDismissed);
  const [open, setOpen] = useState(false);

  if (!data?.newer || !data.latest || dismissed === data.latest) return null;
  const latest = data.latest;

  function hide() {
    try {
      window.localStorage.setItem(DISMISSED_KEY, latest);
    } catch {
      /* not kept; hidden for this visit only */
    }
    setDismissed(latest);
  }

  const hint =
    data.kind === "container"
      ? t("containerHint")
      : data.kind === "source"
        ? t("sourceHint")
        : t("commandHint");

  return (
    <div
      role="status"
      className="border-b border-border bg-primary/5 px-5 py-3 text-sm md:px-8"
    >
      <div className="flex items-start gap-2">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-2">
          <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 py-1.5">
            <ArrowUpCircle className="size-4 shrink-0 text-primary" aria-hidden />
            <span className="font-medium text-foreground">{t("title", { latest })}</span>
            <span className="text-muted-foreground">{t("current", { current: data.current })}</span>
          </p>

          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            {data.download ? (
              <Button asChild size="sm">
                <a href={data.download} target="_blank" rel="noopener noreferrer">
                  <Download /> {t("download")}
                </a>
              </Button>
            ) : data.command ? (
              <Button
                size="sm"
                variant="secondary"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
              >
                {t("howTo")}
                <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
              </Button>
            ) : null}
            {data.notes && (
              <Button asChild size="sm" variant="ghost">
                <a href={data.notes} target="_blank" rel="noopener noreferrer">
                  {t("whatsNew")} <ExternalLink />
                </a>
              </Button>
            )}
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={hide} aria-label={t("hide")}>
          <X /> <span className="hidden sm:inline">{t("hide")}</span>
        </Button>
      </div>

      {data.download && (
        <p className="mt-2 text-xs text-muted-foreground">{t("setupHint")}</p>
      )}
      {!data.download && data.command && open && (
        <div className="mt-3 max-w-3xl space-y-2">
          <p className="text-xs text-muted-foreground">{hint}</p>
          <TerminalBlock label={t("terminal")} command={data.command} />
        </div>
      )}
    </div>
  );
}
