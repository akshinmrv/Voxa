import { CheckCircle2, Loader2, Circle, XCircle } from "lucide-react";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type StepState = "done" | "active" | "pending" | "failed";

function stepState(n: number, current: number, status: JobStatus): StepState {
  if (status === "done") return "done";
  if (status === "failed") {
    if (n < current) return "done";
    if (n === current) return "failed";
    return "pending";
  }
  if (n < current) return "done";
  if (n === current) return "active";
  return "pending";
}

const ICON = {
  done: CheckCircle2,
  active: Loader2,
  pending: Circle,
  failed: XCircle,
} as const;

const COLOR = {
  done: "text-success",
  active: "text-primary",
  pending: "text-fg-subtle",
  failed: "text-danger",
} as const;

/** Seven-step pipeline stepper with a top progress bar. */
export function PipelineProgress({
  steps,
  current,
  status,
}: {
  steps: string[];
  current: number;
  status: JobStatus;
}) {
  const percent =
    status === "done" ? 100 : Math.round((Math.max(current - 1, 0) / steps.length) * 100);

  return (
    <div className="space-y-6">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            status === "failed" ? "bg-danger" : "bg-primary",
          )}
          style={{ width: `${status === "failed" ? 100 : percent}%` }}
        />
      </div>

      <ol className="space-y-1">
        {steps.map((label, i) => {
          const n = i + 1;
          const state = stepState(n, current, status);
          const Icon = ICON[state];
          return (
            <li key={label} className="flex items-center gap-3 py-1.5">
              <Icon
                className={cn(
                  "size-5 shrink-0",
                  COLOR[state],
                  state === "active" && "animate-spin",
                )}
              />
              <span
                className={cn(
                  "type-code text-xs tabular",
                  state === "pending" ? "text-fg-subtle" : "text-muted-foreground",
                )}
              >
                {String(n).padStart(2, "0")}
              </span>
              <span
                className={cn(
                  "text-sm",
                  state === "pending" ? "text-fg-subtle" : "text-foreground",
                  state === "active" && "font-medium",
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
