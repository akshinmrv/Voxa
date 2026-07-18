"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ArrowLeft, Download, AlertTriangle } from "lucide-react";
import type { JobEvent, JobStatus } from "@/lib/types";
import { getJob, jobEventsUrl, resultVideoUrl, resultSrtUrl } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./status-badge";
import { PipelineProgress } from "./pipeline-progress";
import { Loading, BackendError } from "./query-states";

const MAX_LOGS = 500;

export function JobDetail({ jobId }: { jobId: string }) {
  const t = useTranslations("App.job");
  const steps = t.raw("steps") as string[];

  const meta = useQuery({ queryKey: ["job", jobId], queryFn: () => getJob(jobId) });

  const [sseStatus, setSseStatus] = useState<JobStatus | null>(null);
  const [sseStep, setSseStep] = useState<number | null>(null);
  const [sseError, setSseError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const logRef = useRef<HTMLPreElement>(null);

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
        if (data.status === "done" || data.status === "failed") {
          es.close();
          meta.refetch();
        }
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  // Keep the log view pinned to the latest line.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  if (meta.isPending && logs.length === 0 && !sseStatus) return <Loading />;
  if (meta.isError && !sseStatus)
    return <BackendError onRetry={() => meta.refetch()} />;

  const status: JobStatus = sseStatus ?? meta.data?.status ?? "queued";
  const step = sseStep ?? meta.data?.step ?? 0;
  const fileName = meta.data?.fileName ?? jobId;
  const hasVideo = status === "done" && (meta.data?.hasVideo ?? true);
  const hasSrt = status === "done" && (meta.data?.hasSrt ?? false);
  // The server reports the last error line, so the reason is visible without reading logs.
  const failureReason = sseError ?? meta.data?.error ?? null;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link
          href="/app/jobs"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> {t("back")}
        </Link>
      </div>

      <div className="flex items-center justify-between gap-4">
        <h1 className="type-h2 min-w-0 truncate">{fileName}</h1>
        <StatusBadge status={status} />
      </div>

      {status === "done" && hasVideo && (
        <Card>
          <CardHeader>
            <CardTitle>{t("result")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <video
              controls
              className="w-full rounded-md border border-border bg-black"
              src={resultVideoUrl(jobId)}
            />
            <div className="flex flex-wrap gap-3">
              <Button asChild>
                <a href={resultVideoUrl(jobId)} download>
                  <Download /> {t("download")}
                </a>
              </Button>
              {hasSrt && (
                <Button asChild variant="secondary">
                  <a href={resultSrtUrl(jobId)} download>
                    <Download /> {t("downloadSrt")}
                  </a>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
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
