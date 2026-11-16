"use client";

import { useTranslations } from "next-intl";
import { Loader2, Clock, CheckCircle2, XCircle, PencilLine, Square } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const MAP = {
  queued: { variant: "neutral", icon: Clock },
  running: { variant: "info", icon: Loader2 },
  review: { variant: "warning", icon: PencilLine },
  done: { variant: "success", icon: CheckCircle2 },
  failed: { variant: "danger", icon: XCircle },
  stopped: { variant: "neutral", icon: Square },
} as const;

/** A dub's state, word and icon together. One the user stopped isn't shown as failed. */
export function StatusBadge({ status, cancelled }: { status: JobStatus; cancelled?: boolean }) {
  const t = useTranslations("App.status");
  const key = status === "failed" && cancelled ? "stopped" : status;
  const { variant, icon: Icon } = MAP[key];
  return (
    <Badge variant={variant}>
      <Icon className={key === "running" ? "animate-spin" : undefined} />
      {t(key)}
    </Badge>
  );
}
