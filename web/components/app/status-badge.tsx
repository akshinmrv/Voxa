"use client";

import { useTranslations } from "next-intl";
import { Loader2, Clock, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const MAP = {
  queued: { variant: "neutral", icon: Clock },
  running: { variant: "info", icon: Loader2 },
  done: { variant: "success", icon: CheckCircle2 },
  failed: { variant: "danger", icon: XCircle },
} as const;

export function StatusBadge({ status }: { status: JobStatus }) {
  const t = useTranslations("App.status");
  const { variant, icon: Icon } = MAP[status];
  return (
    <Badge variant={variant}>
      <Icon className={status === "running" ? "animate-spin" : undefined} />
      {t(status)}
    </Badge>
  );
}
