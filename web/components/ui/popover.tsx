"use client";

import * as React from "react";
import * as P from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

const Popover = P.Root;
const PopoverTrigger = P.Trigger;
const PopoverAnchor = P.Anchor;
const PopoverClose = P.Close;

function PopoverContent({
  className,
  sideOffset = 6,
  align = "start",
  ...props
}: React.ComponentProps<typeof P.Content>) {
  return (
    <P.Portal>
      <P.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(
          "z-50 w-72 rounded-md border border-border bg-surface-3 p-3 text-ui-body text-foreground shadow-overlay outline-none data-[state=open]:animate-voxa-in data-[state=closed]:animate-voxa-out",
          className,
        )}
        {...props}
      />
    </P.Portal>
  );
}

export { Popover, PopoverTrigger, PopoverAnchor, PopoverClose, PopoverContent };
