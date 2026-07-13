import type { LucideIcon } from "lucide-react";

/** Centered empty state: icon + message + optional action (DESIGN_SYSTEM.md §8.5). */
export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-border bg-surface-1 px-6 py-20 text-center">
      <div className="flex size-12 items-center justify-center rounded-md border border-border bg-surface-2 text-muted-foreground">
        <Icon className="size-6" />
      </div>
      <h2 className="type-h3 mt-4">{title}</h2>
      <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{body}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
