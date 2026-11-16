"use client";

import * as React from "react";
import * as SA from "@radix-ui/react-scroll-area";
import { cn } from "@/lib/utils";

/** A scrolling region with a thin scrollbar that matches the theme (logs, line lists). */
function ScrollArea({
  className,
  viewportClassName,
  viewportRef,
  children,
  ...props
}: React.ComponentProps<typeof SA.Root> & {
  viewportClassName?: string;
  viewportRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <SA.Root className={cn("relative overflow-hidden", className)} {...props}>
      <SA.Viewport ref={viewportRef} className={cn("size-full rounded-[inherit]", viewportClassName)}>
        {children}
      </SA.Viewport>
      <ScrollBar orientation="vertical" />
      <ScrollBar orientation="horizontal" />
      <SA.Corner />
    </SA.Root>
  );
}

function ScrollBar({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<typeof SA.Scrollbar>) {
  return (
    <SA.Scrollbar
      orientation={orientation}
      className={cn(
        "flex touch-none select-none p-0.5 transition-colors duration-(--dur-1)",
        orientation === "vertical" ? "h-full w-2.5" : "h-2.5 flex-col",
        className,
      )}
      {...props}
    >
      <SA.Thumb className="relative flex-1 rounded-full bg-border-strong/60 hover:bg-border-strong" />
    </SA.Scrollbar>
  );
}

export { ScrollArea, ScrollBar };
