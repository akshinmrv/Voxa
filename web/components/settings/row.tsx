"use client";

import { createContext, useContext } from "react";
import { cn } from "@/lib/utils";

/** The setting a search led to, lit for a moment. */
export const FlashContext = createContext<string | null>(null);

/**
 * One setting: what it is on the left, its control on the right; under each other when the
 * window is narrow. Its id is what the search finds and leads to (`setting-<id>`).
 */
export function Row({
  id,
  label,
  hint,
  htmlFor,
  children,
  wide = false,
}: {
  id: string;
  /** None for a control that names itself (a key): it then takes the whole row. */
  label?: string;
  hint?: React.ReactNode;
  /** The control the label names, when it is one field. */
  htmlFor?: string;
  children: React.ReactNode;
  /** A control that needs the whole width (keys, a long text). */
  wide?: boolean;
}) {
  const flash = useContext(FlashContext) === id;
  return (
    <div
      id={`setting-${id}`}
      className={cn(
        "grid gap-x-8 gap-y-2 px-4 py-4 transition-shadow duration-(--dur-2)",
        !wide && label && "md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]",
        flash && "relative z-10 rounded-md shadow-[inset_0_0_0_2px_var(--ring)]",
      )}
    >
      {label && (
        <div className="min-w-0">
          {htmlFor ? (
            <label htmlFor={htmlFor} className="text-ui-body font-medium text-foreground">
              {label}
            </label>
          ) : (
            <p className="text-ui-body font-medium text-foreground">{label}</p>
          )}
          {hint && <div className="mt-1 text-ui-small text-muted-foreground">{hint}</div>}
        </div>
      )}
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** A group of settings in one panel, rows divided by lines. */
export function Group({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      {title && <h3 className="text-ui-label uppercase text-muted-foreground">{title}</h3>}
      <div className="divide-y divide-border rounded-lg border border-border bg-surface-1">
        {children}
      </div>
    </section>
  );
}
