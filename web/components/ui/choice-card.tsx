"use client";

import * as React from "react";
import * as RG from "@radix-ui/react-radio-group";
import { CircleCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Engines and translators as cards rather than <option>s, so their differences show:
 * a name, a line about it, its badges, and when it can't be chosen, why and what to do
 * (VOXA_DESIGN_PLAN.md §9: the reason is always visible, not only in a tooltip).
 */
const ChoiceCards = React.forwardRef<
  React.ComponentRef<typeof RG.Root>,
  React.ComponentProps<typeof RG.Root>
>(({ className, ...props }, ref) => (
  <RG.Root
    ref={ref}
    className={cn("grid gap-2 sm:grid-cols-2 xl:grid-cols-4", className)}
    {...props}
  />
));
ChoiceCards.displayName = "ChoiceCards";

function ChoiceCard({
  value,
  title,
  description,
  badges,
  disabled,
  reason,
  className,
}: {
  value: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Small badges under the description: Offline, Needs a key, Clones a voice… */
  badges?: React.ReactNode;
  disabled?: boolean;
  /** Why it can't be chosen, and the way to fix it (e.g. a link to install it). */
  reason?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <RG.Item
        value={value}
        disabled={disabled}
        className="group relative flex h-full flex-col items-start gap-1 rounded-md border border-border bg-surface-1 p-3 text-left transition-colors duration-(--dur-1) hover:border-border-strong disabled:cursor-not-allowed disabled:hover:border-border data-[state=checked]:border-primary data-[state=checked]:bg-brand-tint"
      >
        <span className="flex w-full items-center justify-between gap-2">
          <span
            className={cn(
              "text-ui-body font-medium text-foreground",
              disabled && "text-muted-foreground",
            )}
          >
            {title}
          </span>
          <RG.Indicator className="text-primary [&_svg]:size-4">
            <CircleCheck />
          </RG.Indicator>
        </span>
        {description && (
          <span className="text-ui-small text-muted-foreground">{description}</span>
        )}
        {badges && <span className="mt-1 flex flex-wrap gap-1.5">{badges}</span>}
      </RG.Item>
      {disabled && reason && <p className="px-1 text-ui-small text-muted-foreground">{reason}</p>}
    </div>
  );
}

export { ChoiceCards, ChoiceCard };
