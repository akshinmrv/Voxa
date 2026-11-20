"use client";

import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ArrowUpCircle, BookOpen, Cpu, FolderOpen, Globe, Keyboard, Loader2 } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { SYSTEM_NAV } from "@/components/app/nav-items";
import { UpdateDetails } from "@/components/app/update-details";
import { getHealth, getOptions, getSettings } from "@/lib/api";
import { useUpdateStatus } from "@/lib/use-update";
import { countJobs, useJobs } from "@/lib/use-jobs";
import { useDesktop } from "@/lib/desktop";
import { SITE } from "@/lib/site";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";
import { GithubIcon } from "@/components/icons/github";
import { cn } from "@/lib/utils";
import { useShell } from "./shell-context";

const DOCS_URL = `${SITE.repo}#readme`;
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

const noSubscribe = () => () => {};
/** The server's host when it isn't this computer (Docker elsewhere, a shared machine). */
function useRemoteHost(): string | null {
  return useSyncExternalStore(
    noSubscribe,
    () => (LOOPBACK.has(window.location.hostname) ? null : window.location.hostname),
    () => null,
  );
}

const item =
  "inline-flex h-full items-center gap-1.5 px-2 text-ui-small text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-2 hover:text-foreground";

/**
 * The strip along the bottom: is the server there, where the models run, what's going, is a
 * newer Voxa out, which Voxa this is (VOXA_DESIGN_PLAN.md §6.6). Each part leads somewhere.
 */
export function StatusBar() {
  const t = useTranslations("App.shell.status");
  const ts = useTranslations("App.settings.advanced");
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 5000,
    retry: false,
  });
  const options = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const count = countJobs(useJobs().data?.jobs);
  const update = useUpdateStatus().data;
  const remote = useRemoteHost();

  const down = health.isError;
  // "auto" uses an NVIDIA GPU when there is one, else the CPU; it never picks Apple's.
  const chosen = settings.data?.advanced?.device ?? "auto";
  const device =
    chosen === "auto"
      ? options.data?.gpu?.cuda
        ? "cuda"
        : "cpu"
      : (chosen as "cpu" | "cuda" | "mps");

  const going = [
    count.running ? t("running", { count: count.running }) : null,
    count.queued ? t("queued", { count: count.queued }) : null,
    count.review ? t("review", { count: count.review }) : null,
  ].filter(Boolean);

  return (
    <footer
      aria-label={t("label")}
      className="flex h-7 shrink-0 items-stretch border-t border-border bg-surface-0 px-1 tabular"
    >
      <Link href="/app/settings" className={item}>
        <span
          aria-hidden
          className={cn("size-2 rounded-full", down ? "animate-pulse bg-warning" : "bg-success")}
        />
        {down ? t("reconnecting") : remote ? t("remote", { host: remote }) : t("local")}
      </Link>

      <Tooltip label={ts("deviceLabel")}>
        <Link href="/app/settings" className={cn(item, "hidden sm:inline-flex")}>
          <Cpu className="size-3.5" aria-hidden />
          {t(device)}
        </Link>
      </Tooltip>

      <Link href="/app/jobs" className={item}>
        {count.running > 0 && (
          <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />
        )}
        {going.length ? going.join(" · ") : t("idle")}
      </Link>

      <span className="flex-1" />

      {update?.newer && update.latest && <UpdateItem />}
      <AboutItem version={health.data?.version ?? update?.current ?? null} />
    </footer>
  );
}

/** "1.19.0 is out": what it is, and how this install gets it. */
function UpdateItem() {
  const tu = useTranslations("App.update");
  const update = useUpdateStatus().data;
  if (!update?.latest) return null;
  return (
    <Popover>
      <PopoverTrigger className={cn(item, "text-primary hover:text-primary")}>
        <ArrowUpCircle className="size-3.5" aria-hidden />
        {tu("newer", { latest: update.latest })}
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="w-96 space-y-3">
        <div>
          <p className="text-ui-section">{tu("title", { latest: update.latest })}</p>
          <p className="text-ui-small text-muted-foreground">
            {tu("current", { current: update.current })}
          </p>
        </div>
        <UpdateDetails update={update} />
      </PopoverContent>
    </Popover>
  );
}

/** "Voxa 1.18.0": the version, and where help is. */
function AboutItem({ version }: { version: string | null }) {
  const t = useTranslations("App.shell");
  const tu = useTranslations("App.update");
  const { openShortcuts } = useShell();
  const desktop = useDesktop();
  const row =
    "flex w-full items-center gap-2.5 rounded-sm px-2 py-1.5 text-left text-ui-body text-foreground transition-colors hover:bg-surface-2 [&_svg]:size-4 [&_svg]:text-muted-foreground";
  return (
    <Popover>
      <PopoverTrigger className={item} aria-label={t("status.about")}>
        {version ? tu("version", { version }) : "Voxa"}
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="w-64 p-1.5">
        <p className="px-2 pb-1.5 pt-1 text-ui-label uppercase text-muted-foreground">
          {t("status.about")}
        </p>
        <Link className={row} href={SYSTEM_NAV.href}>
          <SYSTEM_NAV.icon /> {t("palette.system")}
        </Link>
        <button type="button" className={row} onClick={openShortcuts}>
          <Keyboard /> {t("palette.shortcuts")}
        </button>
        {desktop && (
          <button type="button" className={row} onClick={() => desktop.open_logs()}>
            <FolderOpen /> {t("palette.openLogs")}
          </button>
        )}
        <a className={row} href={DOCS_URL} target="_blank" rel="noopener noreferrer">
          <BookOpen /> {t("palette.docs")}
        </a>
        <a className={row} href={SITE.url} target="_blank" rel="noopener noreferrer">
          <Globe /> {t("palette.website")}
        </a>
        <a className={row} href={SITE.repo} target="_blank" rel="noopener noreferrer">
          <GithubIcon /> {t("palette.github")}
        </a>
      </PopoverContent>
    </Popover>
  );
}
