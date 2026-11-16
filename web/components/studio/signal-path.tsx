"use client";

import { useTranslations } from "next-intl";
import { Pause } from "lucide-react";
import type { JobConfig, JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * The seven steps a dub goes through, as this config will run them: Voxa's "signal path"
 * (VOXA_DESIGN_PLAN.md §5.2). Step 2 separates the speech from the music when that is asked
 * for; subtitles only stop after translating, so speaking and assembling are skipped.
 */
export function usePlannedSteps(config: Pick<JobConfig, "separate" | "subtitlesOnly" | "review">) {
  const t = useTranslations("App");
  const names = t.raw("job.steps") as string[];
  return names.map((name, i) => {
    const n = i + 1;
    return {
      n,
      name: n === 2 && config.separate ? t("studio.separateStep") : name,
      skipped: !!config.subtitlesOnly && n >= 6,
      // With review, the dub waits after translating for the lines to be checked.
      stopsAfter: !!config.review && n === 5,
    };
  });
}

/** The planned path, top to bottom, with the review stop where it falls. */
export function PlannedPath({
  config,
}: {
  config: Pick<JobConfig, "separate" | "subtitlesOnly" | "review">;
}) {
  const t = useTranslations("App.studio");
  const steps = usePlannedSteps(config);
  return (
    <ol className="relative space-y-1.5" aria-label={t("plan")}>
      {/* the line the steps hang on */}
      <span aria-hidden className="absolute bottom-1.5 left-[5px] top-1.5 w-px bg-border" />
      {steps.map((step) => (
        <li key={step.n} className="relative">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden
              className={cn(
                "relative z-10 size-[11px] shrink-0 rounded-full border-2 bg-surface-1",
                step.skipped ? "border-dashed border-border-strong" : "border-primary",
              )}
            />
            <span
              className={cn(
                "flex-1 truncate text-ui-small",
                step.skipped ? "text-fg-subtle line-through" : "text-foreground",
              )}
            >
              {step.name}
            </span>
            {step.skipped && <span className="text-ui-small text-fg-subtle">{t("skipped")}</span>}
          </div>
          {step.stopsAfter && (
            <div className="relative z-10 mt-1.5 flex items-center gap-2 pl-[1px] text-ui-small text-warning">
              <Pause className="size-2.5 shrink-0" aria-hidden />
              {t("reviewStop")}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

/** A dub's progress in seven dots, for lists: done, going, waiting, failed. */
export function MiniPath({ job }: { job: Pick<JobSummary, "status" | "step" | "config"> }) {
  const steps = Array.from({ length: 7 }, (_, i) => i + 1);
  const at = Math.max(job.step, 0);
  return (
    <span aria-hidden className="inline-flex items-center gap-1">
      {steps.map((n) => {
        const skipped = !!job.config.subtitlesOnly && n >= 6;
        const done =
          job.status === "done" ? !skipped : n < at || (job.status === "review" && n <= 5);
        const current =
          (job.status === "running" && n === at) || (job.status === "review" && n === 6);
        const failed = job.status === "failed" && n === Math.max(at, 1);
        return (
          <span
            key={n}
            className={cn(
              "size-1.5 rounded-full",
              failed
                ? "bg-danger"
                : current
                  ? job.status === "review"
                    ? "bg-warning"
                    : "animate-pulse bg-primary"
                  : done
                    ? "bg-primary"
                    : skipped
                      ? "border border-dashed border-border-strong"
                      : "bg-border-strong/50",
            )}
          />
        );
      })}
    </span>
  );
}
