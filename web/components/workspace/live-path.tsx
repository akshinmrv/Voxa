"use client";

import { useTranslations } from "next-intl";
import { Check, Pause, Square, X } from "lucide-react";
import type { JobConfig, JobStatus } from "@/lib/types";
import { usePlannedSteps } from "@/components/studio/signal-path";
import { cn } from "@/lib/utils";

type State = "done" | "current" | "waiting" | "failed" | "stopped" | "skipped" | "next";

/** Each step's state in this run, from the job's status and the last step it reached. */
export function stepStates(
  status: JobStatus,
  at: number,
  cancelled: boolean,
  config: Pick<JobConfig, "subtitlesOnly">,
): State[] {
  return Array.from({ length: 7 }, (_, i) => {
    const n = i + 1;
    if (config.subtitlesOnly && n >= 6) return "skipped";
    if (status === "done") return "done";
    if (status === "review") return n <= 5 ? "done" : n === 6 ? "waiting" : "next";
    if (status === "running") return n < at ? "done" : n === at ? "current" : "next";
    if (status === "failed") {
      const where = Math.max(at, 1);
      return n < where ? "done" : n === where ? (cancelled ? "stopped" : "failed") : "next";
    }
    return "next"; // queued
  });
}

const DOT: Record<State, string> = {
  done: "border-primary bg-primary text-primary-foreground",
  current: "border-primary bg-brand-tint text-primary",
  waiting: "border-warning bg-warning/15 text-warning",
  failed: "border-danger bg-danger text-destructive-foreground",
  stopped: "border-muted-foreground bg-surface-2 text-muted-foreground",
  skipped: "border-dashed border-border-strong bg-transparent text-fg-subtle",
  next: "border-border-strong bg-surface-1 text-fg-subtle",
};

/**
 * The seven steps along a line, as this run goes (VOXA_DESIGN_PLAN.md §5.2, the signal path):
 * done ones filled, the one going pulsing, a review waiting in amber, where it failed or was
 * stopped marked. Narrow, only the line shows; the step's name is in the line above it.
 */
export function LivePath({
  status,
  step,
  cancelled,
  config,
}: {
  status: JobStatus;
  step: number;
  cancelled: boolean;
  config: Pick<JobConfig, "separate" | "subtitlesOnly" | "review">;
}) {
  const t = useTranslations("App");
  const planned = usePlannedSteps(config);
  const states = stepStates(status, step, cancelled, config);

  return (
    <ol className="grid grid-cols-7" aria-label={t("job.progress")}>
      {planned.map((s, i) => {
        const state = states[i];
        const lineDone = states[i + 1] && state === "done" && states[i + 1] !== "next";
        return (
          <li
            key={s.n}
            className="relative flex flex-col items-center gap-2 text-center"
            aria-current={state === "current" ? "step" : undefined}
          >
            {i < 6 && (
              <span
                aria-hidden
                className={cn(
                  "absolute left-1/2 top-[11px] h-0.5 w-full",
                  lineDone ? "bg-primary" : "bg-border",
                )}
              />
            )}
            <span
              className={cn(
                "relative z-10 flex size-6 items-center justify-center rounded-full border-2 [&_svg]:size-3.5",
                DOT[state],
              )}
            >
              {state === "done" ? (
                <Check strokeWidth={3} aria-hidden />
              ) : state === "failed" ? (
                <X strokeWidth={3} aria-hidden />
              ) : state === "stopped" ? (
                <Square className="!size-2.5 fill-current" aria-hidden />
              ) : state === "waiting" ? (
                <Pause aria-hidden />
              ) : state === "current" ? (
                <span className="size-2 animate-pulse rounded-full bg-primary" aria-hidden />
              ) : (
                <span className="font-mono text-[10px]" aria-hidden>
                  {s.n}
                </span>
              )}
            </span>
            <span
              aria-hidden
              className={cn(
                "hidden px-1 text-ui-small leading-tight md:block",
                state === "current" || state === "waiting"
                  ? "font-medium text-foreground"
                  : state === "next" || state === "skipped"
                    ? "text-fg-subtle"
                    : "text-muted-foreground",
                state === "skipped" && "line-through",
              )}
            >
              {s.name}
            </span>
            <span className="sr-only">
              {state === "skipped" ? `${s.name} (${t("studio.skipped")})` : s.name}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
