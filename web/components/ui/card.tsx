import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Card — surface-1 with a thin border and md radius (DESIGN_SYSTEM.md §8.5).
 * Depth in dark UI comes from surface + border, not shadow (§8.4).
 */
function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-card text-card-foreground transition-colors",
        className,
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-1.5 p-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("type-h3 text-card-foreground", className)} {...props} />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("text-sm text-muted-foreground", className)} {...props} />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("p-6 pt-0", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("flex items-center p-6 pt-0", className)} {...props} />
  );
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
