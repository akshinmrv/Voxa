import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Textarea — multi-line text field matching the token system (surface-1 + input border).
 * Native <textarea>, vertically resizable.
 */
const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-y rounded-sm border border-input bg-surface-1 px-3 py-2 text-sm text-foreground transition-colors hover:border-primary/40 placeholder:text-fg-subtle disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Textarea };
