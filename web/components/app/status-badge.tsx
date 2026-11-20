"use client";

import { useTranslations } from "next-intl";
import { Loader2, Clock, CheckCircle2, XCircle, PencilLine, Square } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAP = {
  queued: { variant: "neutral", icon: Clock, tone: "text-muted-foreground" },
  running: { variant: "info", icon: Loader2, tone: "text-info" },
  review: { variant: "warning", icon: PencilLine, tone: "text-warning" },
  done: { variant: "success", icon: CheckCircle2, tone: "text-success" },
  failed: { variant: "danger", icon: XCircle, tone: "text-danger" },
  stopped: { variant: "neutral", icon: Square, tone: "text-muted-foreground" },
} as const;

export type StatusKey = keyof typeof MAP;

/** One the user stopped isn't shown as failed. */
export function statusKey(status: JobStatus, cancelled?: boolean): StatusKey {
  return status === "failed" && cancelled ? "stopped" : status;
}

/** A dub's state, word and icon together. */
export function StatusBadge({ status, cancelled }: { status: JobStatus; cancelled?: boolean }) {
  const t = useTranslations("App.status");
  const key = statusKey(status, cancelled);
  const { variant, icon: Icon } = MAP[key];
  return (
    <Badge variant={variant}>
      <Icon className={key === "running" ? "animate-spin" : undefined} />
      {t(key)}
    </Badge>
  );
}

/** The state as an icon alone, for a list's first column: each has its own shape and name. */
export function StatusIcon({
  status,
  cancelled,
  className,
}: {
  status: JobStatus;
  cancelled?: boolean;
  className?: string;
}) {
  const t = useTranslations("App.status");
  const key = statusKey(status, cancelled);
  const { icon: Icon, tone } = MAP[key];
  return (
    <span role="img" aria-label={t(key)} title={t(key)} className={cn("inline-flex", className)}>
      <Icon
        aria-hidden
        className={cn("size-4 shrink-0", tone, key === "running" && "animate-spin")}
      />
    </span>
  );
}
