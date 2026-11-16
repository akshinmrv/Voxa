"use client";

import * as React from "react";
import * as S from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

/** An on/off setting. Off is an outline that passes 3:1; on is filled with the brand. */
function Switch({ className, ...props }: React.ComponentProps<typeof S.Root>) {
  return (
    <S.Root
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-border-strong bg-surface-2 p-px transition-colors duration-(--dur-2) disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        className,
      )}
      {...props}
    >
      <S.Thumb className="pointer-events-none block size-4 rounded-full bg-muted-foreground transition-transform duration-(--dur-2) ease-standard data-[state=checked]:translate-x-4 data-[state=checked]:bg-primary-foreground" />
    </S.Root>
  );
}

export { Switch };
