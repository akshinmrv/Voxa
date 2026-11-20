"use client";

import { memo } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowRight,
  Download,
  FolderOpen,
  MoreHorizontal,
  RotateCcw,
  SlidersHorizontal,
  Square,
  Trash2,
} from "lucide-react";
import type { JobSummary } from "@/lib/types";
import { resultVideoUrl } from "@/lib/api";
import { Link, useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusIcon } from "@/components/app/status-badge";
import { MiniPath, usePlannedSteps } from "@/components/studio/signal-path";
import { formatDuration } from "@/components/studio/source-picker";
import { revealTarget, type RevealKind } from "./job-actions";

/** What a row can do, given by the list: one set of dialogs and mutations for all its rows. */
export type RowActions = {
  /** null until the server has said whether it can. */
  canReveal: boolean | null;
  stoppingId: string | null;
  askStop: (id: string) => void;
  stopNow: (id: string) => void;
  /** Run a failed or stopped dub again. */
  retry: (id: string) => void;
  retryingId: string | null;
  askRemove: (job: JobSummary) => void;
  reveal: (id: string, file: RevealKind) => void;
  openInStudio: (job: JobSummary) => void;
};

/** When a dub was, as a list says it: the time today, else the day. */
export type WhenLabel = (seconds: number) => string;

const GRID =
  "grid grid-cols-[1rem_minmax(0,1fr)_2rem] items-center gap-x-3 sm:grid-cols-[1rem_minmax(0,1fr)_2.5rem_5rem_2rem] md:grid-cols-[1rem_minmax(0,1fr)_2.5rem_5rem_minmax(0,14rem)_8.5rem_2rem]";

export function jobHref(id: string) {
  return { pathname: "/app/jobs/view", query: { id } } as const;
}

const going = (job: JobSummary) => job.status === "queued" || job.status === "running";

/**
 * One dub in the list: the whole row opens it; its buttons and menus sit above that. Drawn
 * again only when its dub (or what the list gives it) changes: hundreds of rows, refreshed
 * every 2 s while a dub runs.
 */
export const JobRow = memo(function JobRow({
  job,
  when,
  actions,
}: {
  job: JobSummary;
  when: WhenLabel;
  actions: RowActions;
}) {
  const t = useTranslations("App.library");
  const tj = useTranslations("App.jobs");
  const tw = useTranslations("App.job");
  const common = useTranslations("Common");
  const steps = usePlannedSteps(job.config);
  const config = job.config;

  const at = job.finishedAt ?? job.startedAt ?? job.createdAt ?? 0;
  const took =
    job.startedAt && job.finishedAt ? formatDuration(job.finishedAt - job.startedAt) : null;
  const detail = (() => {
    switch (job.status) {
      case "running": {
        const n = Math.max(job.step, 1);
        return { text: t("stepShort", { n, name: steps[n - 1]?.name ?? "" }), tone: "" };
      }
      case "queued":
        return {
          text: tw("waiting", { ahead: Math.max((job.queuePosition ?? 1) - 1, 0) }),
          tone: "",
        };
      case "review":
        return { text: t("waitingReview"), tone: "text-warning" };
      case "done":
        return { text: took ? t("doneAt", { when: when(at), took }) : when(at), tone: "" };
      default:
        return job.cancelled
          ? { text: t("stoppedAt", { when: when(at) }), tone: "" }
          : {
              text: t("failedAt", { when: when(at), reason: job.error ?? tw("failed") }),
              tone: "text-danger",
            };
    }
  })();

  const primary = (() => {
    if (job.status === "running")
      return (
        <Button
          size="xs"
          variant="ghost"
          onClick={() => actions.askStop(job.id)}
          loading={actions.stoppingId === job.id}
        >
          <Square className="fill-current" /> {tw("stop")}
        </Button>
      );
    if (job.status === "queued")
      return (
        <Button
          size="xs"
          variant="ghost"
          onClick={() => actions.stopNow(job.id)}
          loading={actions.stoppingId === job.id}
        >
          {t("cancel")}
        </Button>
      );
    if (job.status === "review")
      return (
        <Button asChild size="xs" variant="secondary">
          <Link href={jobHref(job.id)}>{t("review")}</Link>
        </Button>
      );
    if (job.status === "failed")
      return (
        <Button
          size="xs"
          variant="ghost"
          onClick={() => actions.retry(job.id)}
          loading={actions.retryingId === job.id}
        >
          {actions.retryingId !== job.id && <RotateCcw />}
          <span className="truncate">{job.cancelled ? tw("runAgain") : tw("retry")}</span>
        </Button>
      );
    if (job.status === "done" && actions.canReveal === null) return null;
    if (job.status === "done" && actions.canReveal)
      return (
        <Button size="xs" variant="ghost" onClick={() => actions.reveal(job.id, revealTarget(job))}>
          <FolderOpen /> <span className="truncate">{t("showInFolder")}</span>
        </Button>
      );
    if (job.status === "done" && job.hasVideo)
      return (
        <Button asChild size="xs" variant="ghost">
          <a href={resultVideoUrl(job.id)} download>
            <Download /> <span className="truncate">{t("save")}</span>
          </a>
        </Button>
      );
    return null;
  })();

  const onKeyDown = (event: React.KeyboardEvent<HTMLAnchorElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      const links = Array.from(
        event.currentTarget
          .closest("[data-library]")
          ?.querySelectorAll<HTMLElement>("[data-row-link]") ?? [],
      );
      const next = links[links.indexOf(event.currentTarget) + (event.key === "ArrowDown" ? 1 : -1)];
      if (next) {
        event.preventDefault();
        next.focus();
      }
    } else if (event.key === "Delete" && !going(job)) {
      event.preventDefault();
      actions.askRemove(job);
    }
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <li
          className={`${GRID} group relative px-3 py-2 transition-colors duration-(--dur-1) hover:bg-surface-2 focus-within:bg-surface-2`}
        >
          <StatusIcon status={job.status} cancelled={job.cancelled} />
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <Link
                href={jobHref(job.id)}
                data-row-link
                onKeyDown={onKeyDown}
                className="truncate text-ui-body font-medium outline-none after:absolute after:inset-0 after:content-[''] focus-visible:after:shadow-[inset_0_0_0_2px_var(--ring)]"
              >
                {job.fileName}
              </Link>
              {config.subtitlesOnly ? (
                <Badge variant="neutral" className="shrink-0">
                  {tj("subtitles")}
                </Badge>
              ) : null}
              {config.preview ? (
                <Badge variant="brand" className="shrink-0">
                  {tj("preview", { seconds: config.preview })}
                </Badge>
              ) : null}
            </div>
            {/* Narrow: what the columns say, under the name. */}
            <p className={`truncate text-ui-small text-muted-foreground md:hidden ${detail.tone}`}>
              <span className="font-mono sm:hidden">{config.targetLang} · </span>
              {detail.text}
            </p>
          </div>
          <span className="hidden font-mono text-ui-mono text-muted-foreground sm:block">
            {config.targetLang}
          </span>
          <span className="hidden truncate text-ui-small text-muted-foreground sm:block">
            {config.subtitlesOnly ? "—" : config.tts}
          </span>
          <span className="hidden min-w-0 items-center gap-2 md:flex">
            {going(job) && <MiniPath job={job} />}
            <span
              title={job.status === "failed" && job.error ? job.error : undefined}
              className={`truncate text-ui-small text-muted-foreground ${detail.tone}`}
            >
              {detail.text}
            </span>
          </span>
          <span className="relative z-10 hidden min-w-0 justify-self-end md:flex">{primary}</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon-sm"
                variant="ghost"
                className="relative z-10 size-7 justify-self-end"
                aria-label={t("moreFor", { name: job.fileName })}
                title={common("moreActions")}
              >
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <JobMenuItems kind="dropdown" job={job} actions={actions} />
            </DropdownMenuContent>
          </DropdownMenu>
        </li>
      </ContextMenuTrigger>
      <ContextMenuContent>
        <JobMenuItems kind="context" job={job} actions={actions} />
      </ContextMenuContent>
    </ContextMenu>
  );
});

/** The same items in the ⋯ menu and on a right click. */
function JobMenuItems({
  kind,
  job,
  actions,
}: {
  kind: "dropdown" | "context";
  job: JobSummary;
  actions: RowActions;
}) {
  const t = useTranslations("App.library");
  const tw = useTranslations("App.job");
  const router = useRouter();
  const Item = (kind === "context" ? ContextMenuItem : DropdownMenuItem) as typeof DropdownMenuItem;
  const Separator = (
    kind === "context" ? ContextMenuSeparator : DropdownMenuSeparator
  ) as typeof DropdownMenuSeparator;
  const isGoing = going(job);
  return (
    <>
      <Item onSelect={() => router.push(jobHref(job.id))}>
        <ArrowRight /> {t("open")}
      </Item>
      {actions.canReveal && (
        <Item onSelect={() => actions.reveal(job.id, revealTarget(job))}>
          <FolderOpen /> {t("showInFolder")}
        </Item>
      )}
      {job.status === "done" && job.hasVideo && (
        <Item asChild>
          <a href={resultVideoUrl(job.id)} download>
            <Download /> {tw("download")}
          </a>
        </Item>
      )}
      {job.status === "failed" && (
        <Item onSelect={() => actions.retry(job.id)}>
          <RotateCcw /> {job.cancelled ? tw("runAgain") : tw("retry")}
        </Item>
      )}
      <Item onSelect={() => actions.openInStudio(job)}>
        <SlidersHorizontal /> {tw("useSettings")}
      </Item>
      <Separator />
      {isGoing ? (
        <Item
          onSelect={() =>
            job.status === "running" ? actions.askStop(job.id) : actions.stopNow(job.id)
          }
        >
          <Square /> {job.status === "running" ? tw("stop") : t("cancel")}
        </Item>
      ) : (
        <Item destructive onSelect={() => actions.askRemove(job)}>
          <Trash2 /> {tw("remove")}
        </Item>
      )}
    </>
  );
}
