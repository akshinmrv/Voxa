"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Download, AlertTriangle, PencilLine, Film, Loader2 } from "lucide-react";
import type { JobEvent, JobStatus } from "@/lib/types";
import {
  dubWholeVideo,
  getJob,
  getSettings,
  jobEventsUrl,
  resultVideoUrl,
  resultSrtUrl,
  resultVttUrl,
} from "@/lib/api";
import { useAutoDownload } from "@/lib/use-auto-download";
import { useRouter } from "@/i18n/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "./status-badge";
import { PipelineProgress } from "./pipeline-progress";
import { TranslationEditor } from "./translation-editor";
import { Loading, BackendError } from "./query-states";

const MAX_LOGS = 500;

/**
 * The job page takes its id from `?id=` rather than a `[id]` segment: job ids only exist at
 * run time, and the console `voxa serve` ships is a static build that can't hold dynamic routes.
 */
export function JobDetailFromQuery() {
  const id = useSearchParams().get("id");
  const router = useRouter();
  useEffect(() => {
    if (!id) router.replace("/app/jobs");
  }, [id, router]);
  return id ? <JobDetail key={id} jobId={id} /> : <Loading />;
}

export function JobDetail({ jobId }: { jobId: string }) {
  const t = useTranslations("App.job");
  const steps = t.raw("steps") as string[];
  const router = useRouter();

  const meta = useQuery({ queryKey: ["job", jobId], queryFn: () => getJob(jobId) });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });

  const [sseStatus, setSseStatus] = useState<JobStatus | null>(null);
  const [sseStep, setSseStep] = useState<number | null>(null);
  const [sseError, setSseError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const logRef = useRef<HTMLPreElement>(null);
  // Bumped when the job is voiced (again), to follow that run's stream.
  const [run, setRun] = useState(0);
  const [editing, setEditing] = useState(false);

  // Live pipeline stream. setState happens only inside the event callback.
  useEffect(() => {
    const es = new EventSource(jobEventsUrl(jobId));
    es.onmessage = (e) => {
      const data = JSON.parse(e.data) as JobEvent;
      if (data.type === "log") {
        setLogs((prev) => [...prev, data.line].slice(-MAX_LOGS));
      } else if (data.type === "step") {
        setSseStep(data.step);
      } else if (data.type === "status") {
        setSseStatus(data.status);
        if (data.error) setSseError(data.error);
        if (data.status === "done" || data.status === "failed" || data.status === "review") {
          es.close();
          meta.refetch();
        }
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, run]);

  // A preview leads to the whole video: a job of its own, with the same settings.
  const whole = useMutation({
    mutationFn: () => dubWholeVideo(jobId),
    onSuccess: ({ jobId: next }) =>
      router.push({ pathname: "/app/jobs/view", query: { id: next } }),
  });

  // The job was queued to be voiced: start its page over on the new run's stream.
  function followVoicing() {
    setLogs([]);
    setSseStatus("queued");
    setSseStep(0);
    setSseError(null);
    setEditing(false);
    setRun((n) => n + 1);
  }

  // Keep the log view pinned to the latest line.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const status: JobStatus = sseStatus ?? meta.data?.status ?? "queued";
  const hasVideo = status === "done" && (meta.data?.hasVideo ?? true);

  // Saves the dub the moment the stream reports it finished, if Settings asks for that.
  // Declared above the early returns below, since hooks can't run conditionally.
  useAutoDownload([{ id: jobId, status, hasVideo }],
                  settingsQuery.data?.advanced?.autoDownload ?? false);

  if (meta.isPending && logs.length === 0 && !sseStatus) return <Loading />;
  if (meta.isError && !sseStatus)
    return <BackendError onRetry={() => meta.refetch()} />;

  const step = sseStep ?? meta.data?.step ?? 0;
  const hasSrt = status === "done" && (meta.data?.hasSrt ?? false);
  const subtitlesOnly = !!meta.data?.config.subtitlesOnly;
  // The server reports the last error line, so the reason is visible without reading logs.
  const failureReason = sseError ?? meta.data?.error ?? null;
  const reviewing = status === "review";
  const preview = meta.data?.config.preview ?? null;
  const canEdit = (status === "done" || status === "failed") && !!meta.data?.hasTranslation;

  return (
    <div className="max-w-3xl space-y-6">
      {/* The file's name and the way back are in the header's "Dubs › name". */}
      <div className="flex items-center gap-2">
        <StatusBadge status={status} />
        {preview ? (
          <Badge variant="brand" className="shrink-0">
            {t("previewBadge", { seconds: preview })}
          </Badge>
        ) : null}
      </div>

      {status === "done" && (hasVideo || hasSrt) && (
        <Card>
          <CardHeader>
            <CardTitle>{t("result")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasVideo && (
              // crossOrigin: the console's dev server reads the subtitles from the API's port.
              <video
                controls
                crossOrigin="anonymous"
                className="w-full rounded-md border border-border bg-black"
                src={resultVideoUrl(jobId)}
              >
                {/* Drawn-on subtitles are in the picture already; a track in the MP4 isn't
                    shown by browsers, so the player gets the subtitles as WebVTT. */}
                {hasSrt && meta.data?.config.subtitlesInVideo !== "hard" && (
                  <track
                    kind="subtitles"
                    src={resultVttUrl(jobId)}
                    srcLang={meta.data?.config.targetLang}
                    label={meta.data?.config.targetLang}
                    default={subtitlesOnly || meta.data?.config.subtitlesInVideo === "soft"}
                  />
                )}
              </video>
            )}
            <div className="flex flex-wrap gap-3">
              {hasVideo && (
                <Button asChild>
                  <a href={resultVideoUrl(jobId)} download>
                    <Download /> {t("download")}
                  </a>
                </Button>
              )}
              {hasSrt && (
                <Button asChild variant="secondary">
                  <a href={resultSrtUrl(jobId)} download>
                    <Download /> {t("downloadSrt")}
                  </a>
                </Button>
              )}
            </div>
            {preview ? (
              <div className="space-y-2 border-t border-border pt-4">
                <p className="text-sm text-muted-foreground">
                  {t("previewDone", { seconds: preview })}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={() => whole.mutate()} disabled={whole.isPending}>
                    {whole.isPending ? <Loader2 className="animate-spin" /> : <Film />}
                    {subtitlesOnly ? t("wholeVideoSubtitles") : t("wholeVideo")}
                  </Button>
                  {whole.isError && (
                    <span className="text-sm text-danger">{(whole.error as Error).message}</span>
                  )}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {reviewing && meta.data && (
        <TranslationEditor
          jobId={jobId}
          status={status}
          config={meta.data.config}
          onVoice={followVoicing}
        />
      )}

      {status === "failed" && (
        <div className="flex gap-3 rounded-md border border-danger/25 bg-danger/10 p-4">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" />
          <div className="min-w-0 space-y-2">
            {failureReason && (
              <p className="break-words font-mono text-sm text-foreground">{failureReason}</p>
            )}
            <p className="text-sm text-muted-foreground">{t("failed")}</p>
          </div>
        </div>
      )}

      {canEdit &&
        meta.data &&
        (editing ? (
          <TranslationEditor
            jobId={jobId}
            status={status}
            config={meta.data.config}
            onVoice={followVoicing}
          />
        ) : (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            <PencilLine /> {t("editTranslation")}
          </Button>
        ))}

      <Card>
        <CardHeader>
          <CardTitle>{t("progress")}</CardTitle>
        </CardHeader>
        <CardContent>
          <PipelineProgress steps={steps} current={step} status={status} />
        </CardContent>
      </Card>

      <div>
        <h2 className="type-label mb-2 text-muted-foreground">{t("logs")}</h2>
        <pre
          ref={logRef}
          className="max-h-72 overflow-auto rounded-md border border-border bg-surface-1 p-4"
        >
          <code className="type-code text-xs text-muted-foreground">
            {logs.length ? logs.join("\n") : t("connecting")}
          </code>
        </pre>
      </div>
    </div>
  );
}
