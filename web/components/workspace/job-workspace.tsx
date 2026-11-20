"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Download,
  FileText,
  Film,
  FolderOpen,
  MoreHorizontal,
  SlidersHorizontal,
  Square,
  Trash2,
} from "lucide-react";
import type { JobEvent, JobStatus, JobSummary } from "@/lib/types";
import {
  dubWholeVideo,
  getJob,
  getSettings,
  jobEventsUrl,
  resultSrtUrl,
  resultVideoUrl,
  resultVttUrl,
} from "@/lib/api";
import { useAutoDownload } from "@/lib/use-auto-download";
import { useDates } from "@/lib/dates";
import { useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StatusBadge } from "@/components/app/status-badge";
import { BackendError, Loading } from "@/components/app/query-states";
import { formatDuration } from "@/components/studio/source-picker";
import { usePlannedSteps } from "@/components/studio/signal-path";
import {
  revealTarget,
  useCanReveal,
  useJobDialogs,
  useOpenInStudio,
  useReveal,
} from "@/components/library/job-actions";
import { LivePath } from "./live-path";
import { LogPanel } from "./log-panel";
import { LinesView } from "./lines-view";

const MAX_LOGS = 2000;

/** Now, every second: for "2:41 so far" while a dub runs. */
function useNow(running: boolean): number {
  const subscribe = (tick: () => void) => {
    if (!running) return () => {};
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  };
  return useSyncExternalStore(
    subscribe,
    () => Math.floor(Date.now() / 1000),
    () => 0,
  );
}

/**
 * The dub's page takes its id from `?id=` rather than a `[id]` segment: job ids only exist at
 * run time, and the console `voxa serve` ships is a static build that can't hold dynamic routes.
 */
export function JobWorkspaceFromQuery() {
  const id = useSearchParams().get("id");
  const router = useRouter();
  useEffect(() => {
    if (!id) router.replace("/app/jobs");
  }, [id, router]);
  return id ? <JobWorkspace key={id} jobId={id} /> : <Loading />;
}

/** The live part of a job: what its event stream has said since the page opened. */
function useJobStream(jobId: string, run: number, onChange: () => void) {
  const [state, setState] = useState<{
    status: JobStatus | null;
    step: number | null;
    error: string | null;
    logs: string[];
  }>({ status: null, step: null, error: null, logs: [] });

  useEffect(() => {
    const es = new EventSource(jobEventsUrl(jobId));
    es.onmessage = (e) => {
      const data = JSON.parse(e.data) as JobEvent;
      if (data.type === "log") {
        setState((s) => ({ ...s, logs: [...s.logs, data.line].slice(-MAX_LOGS) }));
      } else if (data.type === "step") {
        setState((s) => ({ ...s, step: data.step }));
      } else if (data.type === "status") {
        setState((s) => ({ ...s, status: data.status, error: data.error ?? s.error }));
        onChange();
        if (data.status === "done" || data.status === "failed" || data.status === "review") {
          es.close();
        }
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // A new run (voiced again) follows a new stream; onChange is stable enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, run]);

  return [state, setState] as const;
}

export function JobWorkspace({ jobId }: { jobId: string }) {
  const t = useTranslations("App.job");
  const tn = useTranslations("App.newJob");
  const ts = useTranslations("App.studio");
  const tl = useTranslations("App.library");
  const common = useTranslations("Common");
  const dates = useDates();
  const router = useRouter();
  const queryClient = useQueryClient();

  const meta = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    // Its place in the queue and its start time change without an event of its own.
    refetchInterval: (q) =>
      q.state.data?.status === "queued" || q.state.data?.status === "running" ? 3000 : false,
  });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const [run, setRun] = useState(0);
  const [stream, setStream] = useJobStream(jobId, run, () => {
    meta.refetch();
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  });
  const [tab, setTab] = useState<string | null>(null);

  const job: JobSummary | undefined = meta.data;
  const status: JobStatus = stream.status ?? job?.status ?? "queued";
  const going = status === "queued" || status === "running";
  const now = useNow(status === "running");
  const hasVideo = status === "done" && (job?.hasVideo ?? true);

  // Saves the dub the moment the stream reports it finished, if Settings asks for that.
  useAutoDownload(
    [{ id: jobId, status, hasVideo }],
    settingsQuery.data?.advanced?.autoDownload ?? false,
  );

  const { askStop, askRemove, stoppingId, dialogs } = useJobDialogs({
    onRemoved: () => router.replace("/app/jobs"),
  });
  const canReveal = useCanReveal();
  const reveal = useReveal();
  const openWithSettings = useOpenInStudio();
  // A preview leads to the whole video: a job of its own, with the same settings.
  const whole = useMutation({
    mutationFn: () => dubWholeVideo(jobId),
    onSuccess: ({ jobId: next }) =>
      router.push({ pathname: "/app/jobs/view", query: { id: next } }),
  });

  const steps = usePlannedSteps(
    job?.config ?? { separate: false, subtitlesOnly: false, review: false },
  );

  if (meta.isPending && !stream.status) return <Loading />;
  if ((meta.isError || !job) && !stream.status)
    return <BackendError onRetry={() => meta.refetch()} />;
  if (!job) return <Loading />;

  const config = job.config;
  const step = stream.step ?? job.step ?? 0;
  const cancelled = status === "failed" && (job.cancelled ?? false);
  const reason = stream.error ?? job.error ?? null;
  const hasSrt = status === "done" && (job.hasSrt ?? false);
  const preview = config.preview ?? null;
  const canEdit =
    (status === "done" || status === "failed" || status === "review") && !!job.hasTranslation;
  const took =
    job.startedAt && job.finishedAt && !going
      ? formatDuration(job.finishedAt - job.startedAt)
      : null;
  const elapsed =
    status === "running" && job.startedAt && now
      ? formatDuration(Math.max(0, now - job.startedAt))
      : null;

  // The job's settings as the Studio's choices, to make another dub from.
  const openInStudio = () => openWithSettings(config);
  const stopping = stoppingId === jobId;
  const showInFolder = (file = revealTarget({ status, hasVideo, hasSrt })) =>
    reveal.mutate({ id: jobId, file });

  // Voiced (again): the page follows the new run's stream.
  function followVoicing() {
    setStream({ status: "queued", step: 0, error: null, logs: [] });
    setRun((n) => n + 1);
    setTab(null);
  }

  const stepName = steps[Math.max(step, 1) - 1]?.name ?? "";
  const line = (() => {
    if (status === "queued")
      return t("waiting", { ahead: Math.max((job.queuePosition ?? 1) - 1, 0) });
    if (status === "running")
      return `${t("stepOf", { n: Math.max(step, 1), total: 7, name: stepName })}${
        elapsed ? ` · ${t("elapsed", { time: elapsed })}` : ""
      }`;
    if (status === "review") return t("waitingReview");
    return took ? t("took", { time: took }) : null;
  })();

  const header = (
    <div className="flex flex-wrap items-center gap-2">
      <StatusBadge status={status} cancelled={cancelled} />
      {preview ? <Badge variant="brand">{t("previewBadge", { seconds: preview })}</Badge> : null}
      <Badge variant="outline" className="font-mono">
        {config.targetLang}
      </Badge>
      <span className="text-ui-small text-muted-foreground">
        {config.translator}
        {config.subtitlesOnly ? "" : ` → ${config.tts}`}
      </span>
      {job.createdAt ? (
        <span className="text-ui-small text-fg-subtle">
          · {t("made", { date: dates.dateTime(new Date(job.createdAt * 1000)) })}
        </span>
      ) : null}
      <span className="flex-1" />
      {going && (
        <Button size="sm" variant="outline" onClick={() => askStop(jobId)} loading={stopping}>
          <Square className="fill-current" /> {stopping ? t("stopping") : t("stop")}
        </Button>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="icon-sm" variant="ghost" aria-label={common("moreActions")}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {canReveal && (
            <DropdownMenuItem onSelect={() => showInFolder()}>
              <FolderOpen /> {tl("showInFolder")}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={openInStudio}>
            <SlidersHorizontal /> {t("useSettings")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            destructive
            disabled={going}
            onSelect={() =>
              askRemove({ id: jobId, fileName: job.fileName, status, hasVideo, hasSrt })
            }
          >
            <Trash2 /> {t("remove")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );

  const progress = (
    <div className="space-y-3 rounded-lg border border-border bg-surface-1 p-4">
      <LivePath status={status} step={step} cancelled={cancelled} config={config} />
      {line && (
        <p className="text-ui-small text-muted-foreground" aria-live="polite">
          {line}
        </p>
      )}
    </div>
  );

  const log = <LogPanel lines={stream.logs} live={going} emptyText={t("connecting")} />;

  const problem = status === "failed" && (
    <div
      className={
        cancelled
          ? "flex gap-3 rounded-lg border border-border bg-surface-1 p-4"
          : "flex gap-3 rounded-lg border border-danger/30 bg-danger/10 p-4"
      }
    >
      {cancelled ? (
        <Square className="mt-0.5 size-4 shrink-0 fill-current text-muted-foreground" />
      ) : (
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
      )}
      <div className="min-w-0 flex-1 space-y-2">
        {cancelled ? (
          <p className="text-ui-body">{t("stoppedBody")}</p>
        ) : (
          <>
            {reason && (
              <p className="break-words font-mono text-ui-small text-foreground">{reason}</p>
            )}
            <p className="text-ui-small text-muted-foreground">{t("failed")}</p>
          </>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" variant="secondary" onClick={openInStudio}>
            <SlidersHorizontal /> {t("useSettings")}
          </Button>
          {!cancelled && (
            <Button size="sm" variant="ghost" onClick={() => setTab("log")}>
              <FileText /> {t("tabLog")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );

  const result = status === "done" && (hasVideo || hasSrt) && (
    <div className="space-y-4">
      {hasVideo && (
        // crossOrigin: the console's dev server reads the subtitles from the API's port.
        <video
          controls
          crossOrigin="anonymous"
          className="aspect-video w-full rounded-lg border border-border bg-black"
          src={resultVideoUrl(jobId)}
        >
          {/* Drawn-on subtitles are in the picture already; a track in the MP4 isn't shown by
              browsers, so the player gets the subtitles as WebVTT. */}
          {hasSrt && config.subtitlesInVideo !== "hard" && (
            <track
              kind="subtitles"
              src={resultVttUrl(jobId)}
              srcLang={config.targetLang}
              label={config.targetLang}
              default={!!config.subtitlesOnly || config.subtitlesInVideo === "soft"}
            />
          )}
        </video>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <section
          aria-labelledby="files"
          className="rounded-lg border border-border bg-surface-1 p-4"
        >
          <h2 id="files" className="mb-3 text-ui-label uppercase text-muted-foreground">
            {t("files")}
          </h2>
          <div className="flex flex-wrap gap-2">
            {hasVideo && (
              <Button asChild size="sm">
                <a href={resultVideoUrl(jobId)} download>
                  <Download /> {t("download")}
                </a>
              </Button>
            )}
            {hasSrt && (
              <Button asChild size="sm" variant="secondary">
                <a href={resultSrtUrl(jobId)} download>
                  <Download /> {t("downloadSrt")}
                </a>
              </Button>
            )}
            {canReveal && (
              <Button size="sm" variant="ghost" onClick={() => showInFolder()}>
                <FolderOpen /> {tl("showInFolder")}
              </Button>
            )}
          </div>
          {preview ? (
            <div className="mt-4 space-y-2 border-t border-border pt-4">
              <p className="text-ui-small text-muted-foreground">
                {t("previewDone", { seconds: preview })}
              </p>
              <Button size="sm" onClick={() => whole.mutate()} loading={whole.isPending}>
                <Film />
                {config.subtitlesOnly ? t("wholeVideoSubtitles") : t("wholeVideo")}
              </Button>
              {whole.isError && (
                <p className="text-ui-small text-danger">{(whole.error as Error).message}</p>
              )}
            </div>
          ) : null}
        </section>
        <section
          aria-labelledby="settings"
          className="rounded-lg border border-border bg-surface-1 p-4"
        >
          <h2 id="settings" className="mb-3 text-ui-label uppercase text-muted-foreground">
            {t("settings")}
          </h2>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-ui-small">
            <dt className="text-muted-foreground">{ts("sectionTranslation")}</dt>
            <dd>{config.translator}</dd>
            {!config.subtitlesOnly && (
              <>
                <dt className="text-muted-foreground">{ts("sectionVoice")}</dt>
                <dd className="truncate">
                  {config.tts}
                  {config.edgeVoice ? ` · ${config.edgeVoice}` : ""}
                  {config.tts === "openai" ? ` · ${config.openaiVoice}` : ""}
                </dd>
              </>
            )}
            <dt className="text-muted-foreground">{tn("whisperModel")}</dt>
            <dd>{config.whisperModel}</dd>
            {took && (
              <>
                <dt className="text-muted-foreground">⏱</dt>
                <dd>{t("took", { time: took })}</dd>
              </>
            )}
          </dl>
          <Button size="sm" variant="ghost" className="mt-3 -ml-2" onClick={openInStudio}>
            <SlidersHorizontal /> {t("useSettings")}
          </Button>
        </section>
      </div>
    </div>
  );

  const editor = canEdit && (
    <LinesView
      jobId={jobId}
      status={status}
      config={config}
      hasDub={hasVideo}
      hasSource={!!job.hasSource}
      onVoice={followVoicing}
    />
  );

  // Going, or waiting for review: one page, nothing to switch between. Done or failed: tabs.
  const body = going ? (
    <div className="space-y-4">
      {progress}
      {log}
    </div>
  ) : status === "review" ? (
    <div className="space-y-4">
      {progress}
      {editor}
      {log}
    </div>
  ) : (
    <Tabs value={tab ?? "main"} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="main">
          {status === "done" ? t("tabResult") : t("tabOverview")}
        </TabsTrigger>
        {canEdit && <TabsTrigger value="lines">{t("tabLines")}</TabsTrigger>}
        <TabsTrigger value="log">{t("tabLog")}</TabsTrigger>
      </TabsList>
      <TabsContent value="main" className="space-y-4">
        {problem}
        {result}
        {progress}
      </TabsContent>
      {/* Kept mounted while another tab shows, so what was typed into the lines stays. */}
      {canEdit && (
        <TabsContent value="lines" forceMount className="data-[state=inactive]:hidden">
          {editor}
        </TabsContent>
      )}
      <TabsContent value="log">{log}</TabsContent>
    </Tabs>
  );

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      {header}
      {body}

      {dialogs}
    </div>
  );
}
