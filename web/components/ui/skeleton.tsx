import * as React from "react";
import { cn } from "@/lib/utils";

/** The shape of what's loading, shown after a moment instead of a spinner. */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-sm bg-surface-2", className)}
      {...props}
    />
  );
}

export { Skeleton };
