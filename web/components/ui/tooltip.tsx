"use client";

import * as React from "react";
import * as Tip from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";
import { Kbd } from "./kbd";

/** One per app: tooltips wait 400 ms, then the next one opens at once. */
function TooltipProvider({
  delayDuration = 400,
  skipDelayDuration = 200,
  ...props
}: React.ComponentProps<typeof Tip.Provider>) {
  return <Tip.Provider delayDuration={delayDuration} skipDelayDuration={skipDelayDuration} {...props} />;
}

const TooltipRoot = Tip.Root;
const TooltipTrigger = Tip.Trigger;

function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: React.ComponentProps<typeof Tip.Content>) {
  return (
    <Tip.Portal>
      <Tip.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 max-w-72 rounded-sm border border-border bg-surface-3 px-2 py-1 text-ui-small text-foreground shadow-overlay data-[state=delayed-open]:animate-voxa-fade-in data-[state=instant-open]:animate-voxa-fade-in data-[state=closed]:animate-voxa-fade-out",
          className,
        )}
        {...props}
      />
    </Tip.Portal>
  );
}

/**
 * The usual case: a label (and its shortcut) on the element it wraps. An icon-only button
 * still needs its own aria-label; a tooltip doesn't name it for a screen reader.
 */
function Tooltip({
  label,
  shortcut,
  side,
  children,
}: {
  label: React.ReactNode;
  shortcut?: string;
  side?: React.ComponentProps<typeof Tip.Content>["side"];
  children: React.ReactNode;
}) {
  return (
    <TooltipRoot>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side={side}>
        <span className="flex items-center gap-2">
          {label}
          {shortcut && <Kbd>{shortcut}</Kbd>}
        </span>
      </TooltipContent>
    </TooltipRoot>
  );
}

export { Tooltip, TooltipProvider, TooltipRoot, TooltipTrigger, TooltipContent };
