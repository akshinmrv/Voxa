"use client";

import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, ListChecks, Plus, Search } from "lucide-react";
import { getSettings } from "@/lib/api";
import { useDates } from "@/lib/dates";
import { isTyping } from "@/lib/shortcuts";
import type { JobSummary } from "@/lib/types";
import { useAutoDownload } from "@/lib/use-auto-download";
import { useJobs } from "@/lib/use-jobs";
import { useLanguageNames } from "@/lib/use-language-names";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/app/empty-state";
import { BackendError, Loading } from "@/components/app/query-states";
import { JobRow, type RowActions, type WhenLabel } from "./job-row";
import {
  useCanReveal,
  useJobDialogs,
  useOpenInStudio,
  useReveal,
  type RevealKind,
} from "./job-actions";

const STATUSES = ["all", "going", "review", "done", "failed", "stopped"] as const;
type StatusFilter = (typeof STATUSES)[number];

function matches(job: JobSummary, status: StatusFilter): boolean {
  switch (status) {
    case "all":
      return true;
    case "going":
      return job.status === "queued" || job.status === "running";
    case "failed":
      return job.status === "failed" && !job.cancelled;
    case "stopped":
      return job.status === "failed" && !!job.cancelled;
    default:
      return job.status === status;
  }
}

/** When a dub was, for sorting and grouping: its last run's end, or start, or its making. */
const whenOf = (job: JobSummary) => job.finishedAt ?? job.startedAt ?? job.createdAt ?? 0;

function startOfToday(): number {
  const day = new Date();
  day.setHours(0, 0, 0, 0);
  return day.getTime() / 1000;
}

/** The start of today, in epoch seconds; it moves on at midnight. */
function useToday(): number {
  return useSyncExternalStore(
    (tick) => {
      const id = setInterval(tick, 60_000);
      return () => clearInterval(id);
    },
    startOfToday,
    () => 0,
  );
}

/**
 * The Dubs page (VOXA_DESIGN_PLAN.md §8.5): every dub, going and queued first, then today's
 * and earlier ones; a search by file name and filters by state and language; each row opens
 * its dub, and does what it needs next (stop, check, show in folder) from its own buttons,
 * its ⋯ menu or a right click.
 */
export function LibraryView() {
  const t = useTranslations("App.library");
  const tj = useTranslations("App.jobs");
  const ts = useTranslations("App.status");
  const locale = useLocale();
  const query = useJobs();
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const names = useLanguageNames();
  const today = useToday();
  const dates = useDates();
  const canReveal = useCanReveal();
  const reveal = useReveal();
  const openInStudio = useOpenInStudio();
  const { askStop, stopNow, askRemove, stoppingId, dialogs } = useJobDialogs();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [lang, setLang] = useState("all");
  const searchBox = useRef<HTMLInputElement>(null);
  // Typing stays quick: the list follows a moment later when there are hundreds of rows.
  const searched = useDeferredValue(search);

  const revealJob = reveal.mutate;
  const revealIt = useCallback(
    (id: string, file: RevealKind) => revealJob({ id, file }),
    [revealJob],
  );
  const studioWith = useCallback((job: JobSummary) => openInStudio(job.config), [openInStudio]);
  // The same object while nothing in it changes, so unchanged rows aren't drawn again.
  const actions: RowActions = useMemo(
    () => ({
      canReveal,
      stoppingId,
      askStop,
      stopNow,
      askRemove,
      reveal: revealIt,
      openInStudio: studioWith,
    }),
    [canReveal, stoppingId, askStop, stopNow, askRemove, revealIt, studioWith],
  );

  // Saves a dub the moment it finishes, if the operator asked for that in Settings.
  useAutoDownload(query.data?.jobs, settings.data?.advanced?.autoDownload ?? false);

  // "/" goes to the search, as in a browser's lists.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTyping(event.target)) return;
      event.preventDefault();
      searchBox.current?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const when: WhenLabel = useMemo(() => {
    const year = new Date(today * 1000).getFullYear();
    return (seconds: number) => {
      const at = new Date(seconds * 1000);
      return seconds >= today ? dates.time(at) : dates.day(at, at.getFullYear() !== year);
    };
  }, [dates, today]);

  const jobs = useMemo(() => query.data?.jobs ?? [], [query.data]);
  const langs = useMemo(
    () => [...new Set(jobs.map((job) => job.config.targetLang))].sort(),
    [jobs],
  );
  const shown = useMemo(() => {
    const needle = searched.trim().toLocaleLowerCase(locale);
    return jobs.filter(
      (job) =>
        matches(job, status) &&
        (lang === "all" || job.config.targetLang === lang) &&
        (!needle || job.fileName.toLocaleLowerCase(locale).includes(needle)),
    );
  }, [jobs, status, lang, searched, locale]);

  const groups = useMemo(() => {
    const goingNow = shown
      .filter((job) => job.status === "running" || job.status === "queued")
      .sort((a, b) =>
        a.status !== b.status
          ? a.status === "running"
            ? -1
            : 1
          : (a.queuePosition ?? 0) - (b.queuePosition ?? 0) || whenOf(a) - whenOf(b),
      );
    const rest = shown
      .filter((job) => job.status !== "running" && job.status !== "queued")
      .sort((a, b) => whenOf(b) - whenOf(a));
    return [
      { id: "going", title: t("going"), jobs: goingNow },
      { id: "today", title: t("today"), jobs: rest.filter((job) => whenOf(job) >= today) },
      { id: "earlier", title: t("earlier"), jobs: rest.filter((job) => whenOf(job) < today) },
    ].filter((group) => group.jobs.length);
  }, [shown, today, t]);

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data) return <BackendError onRetry={() => query.refetch()} />;

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={ListChecks}
        title={tj("emptyTitle")}
        body={tj("emptyBody")}
        action={
          <Button asChild>
            <Link href="/app">{tj("emptyCta")}</Link>
          </Button>
        }
      />
    );
  }

  const filtered = status !== "all" || lang !== "all" || !!search.trim();
  const statusName = (value: StatusFilter) =>
    value === "all" ? t("statusAll") : value === "going" ? t("statusGoing") : ts(value);

  return (
    <div className="space-y-5" data-library>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-64">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
            aria-hidden
          />
          <Input
            ref={searchBox}
            type="search"
            aria-label={t("search")}
            placeholder={t("search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && search) {
                e.preventDefault();
                setSearch("");
              } else if (e.key === "ArrowDown") {
                const first = document.querySelector<HTMLElement>("[data-library] [data-row-link]");
                if (first) {
                  e.preventDefault();
                  first.focus();
                }
              }
            }}
            className="h-8 pl-8 text-ui-body"
          />
        </div>
        <FilterMenu
          label={t("status")}
          value={status}
          valueName={statusName(status)}
          onChange={(value) => setStatus(value as StatusFilter)}
          options={STATUSES.map((value) => ({ value, name: statusName(value) }))}
        />
        <FilterMenu
          label={t("language")}
          value={lang}
          valueName={lang === "all" ? t("languageAll") : names(lang)}
          onChange={setLang}
          options={[
            { value: "all", name: t("languageAll") },
            ...langs.map((code) => ({ value: code, name: `${names(code)} · ${code}` })),
          ]}
        />
        <span className="text-ui-small text-fg-subtle" aria-live="polite">
          {filtered
            ? t("countOf", { shown: shown.length, total: jobs.length })
            : t("count", { total: jobs.length })}
        </span>
        <span className="flex-1" />
        <Button asChild size="sm">
          <Link href="/app">
            <Plus /> {t("newDub")}
          </Link>
        </Button>
      </div>

      {groups.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-surface-1 px-6 py-12 text-center">
          <p className="text-ui-body text-muted-foreground">{t("noMatch")}</p>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setSearch("");
              setStatus("all");
              setLang("all");
            }}
          >
            {t("clearFilters")}
          </Button>
        </div>
      ) : (
        groups.map((group) => (
          <section key={group.id} aria-labelledby={`dubs-${group.id}`} className="space-y-2">
            <h2 id={`dubs-${group.id}`} className="text-ui-label uppercase text-muted-foreground">
              {group.title} <span className="text-fg-subtle">· {group.jobs.length}</span>
            </h2>
            <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
              {group.jobs.map((job) => (
                <JobRow key={job.id} job={job} when={when} actions={actions} />
              ))}
            </ul>
          </section>
        ))
      )}
      {dialogs}
    </div>
  );
}

/** A filter as a button that says what it's set to, with its choices in a menu. */
function FilterMenu({
  label,
  value,
  valueName,
  options,
  onChange,
}: {
  label: string;
  value: string;
  valueName: string;
  options: { value: string; name: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className={value !== "all" ? "border-primary/50 text-foreground" : undefined}
        >
          <span className="text-muted-foreground">{label}:</span> {valueName}
          <ChevronDown className="text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              {option.name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
