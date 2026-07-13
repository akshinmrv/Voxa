"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ListChecks, FileVideo } from "lucide-react";
import { listJobs } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "./empty-state";
import { StatusBadge } from "./status-badge";
import { BackendError, Loading } from "./query-states";

export function JobsView() {
  const t = useTranslations("App.jobs");
  const query = useQuery({
    queryKey: ["jobs"],
    queryFn: listJobs,
    refetchInterval: 4000, // keep the list fresh while jobs run
  });

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data)
    return <BackendError onRetry={() => query.refetch()} />;

  const jobs = [...query.data.jobs].reverse();

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={ListChecks}
        title={t("emptyTitle")}
        body={t("emptyBody")}
        action={
          <Button asChild>
            <Link href="/app">{t("emptyCta")}</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <Link key={job.id} href={`/app/jobs/${job.id}`} className="block">
          <Card className="flex items-center gap-4 p-4 hover:border-primary/40">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-2 text-primary">
              <FileVideo className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{job.fileName}</p>
              <p className="type-code text-xs text-muted-foreground">
                {job.config.targetLang} · {job.config.translator} · {job.config.tts}
              </p>
            </div>
            <StatusBadge status={job.status} />
          </Card>
        </Link>
      ))}
    </div>
  );
}
