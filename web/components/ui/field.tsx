import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Field — a labelled form row. Wires the visible <label> to its control via
 * htmlFor/id so clicks and screen readers behave (DESIGN_SYSTEM.md §15).
 */
export function Field({
  id,
  label,
  hint,
  className,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <label htmlFor={id} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
