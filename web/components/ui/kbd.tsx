import * as React from "react";
import { cn } from "@/lib/utils";

/** A key or shortcut as the keyboard shows it: Ctrl+K, Esc. */
function Kbd({ className, ...props }: React.ComponentProps<"kbd">) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-[4px] border border-border bg-surface-2 px-1.5 font-mono text-[0.6875rem] leading-none text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export { Kbd };
