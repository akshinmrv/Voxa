"use client";

import * as React from "react";
import * as TG from "@radix-ui/react-toggle-group";
import { cn } from "@/lib/utils";

export type SegmentedItem<V extends string> = {
  value: V;
  label: React.ReactNode;
  icon?: React.ReactNode;
  disabled?: boolean;
};

/**
 * One choice of a few, side by side: File · Link, Dub · Subtitles only, Original · Dub.
 * Unlike a toggle group, one is always chosen: clicking the chosen one keeps it.
 */
function SegmentedControl<V extends string>({
  value,
  onValueChange,
  items,
  className,
  size = "default",
  ...props
}: {
  value: V;
  onValueChange: (value: V) => void;
  items: SegmentedItem<V>[];
  className?: string;
  size?: "sm" | "default";
  "aria-label"?: string;
  "aria-labelledby"?: string;
}) {
  return (
    <TG.Root
      type="single"
      value={value}
      onValueChange={(next) => next && onValueChange(next as V)}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-sm border border-border bg-surface-1 p-0.5",
        className,
      )}
      {...props}
    >
      {items.map((item) => (
        <TG.Item
          key={item.value}
          value={item.value}
          disabled={item.disabled}
          className={cn(
            "inline-flex items-center justify-center gap-1.5 rounded-[4px] px-3 font-medium text-muted-foreground transition-colors duration-(--dur-1) hover:text-foreground disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-surface-3 data-[state=on]:text-foreground data-[state=on]:shadow-[inset_0_0_0_1px_var(--border)] [&_svg]:size-4",
            size === "sm" ? "h-7 text-ui-small" : "h-8 text-ui-body",
          )}
        >
          {item.icon}
          {item.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}

export { SegmentedControl };
