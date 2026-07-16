import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Input — styled text field matching the token system (surface-1 + input border).
 * Native <input>, so it stays accessible and keyboard-friendly with zero JS.
 */
const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-sm border border-input bg-surface-1 px-3 text-sm text-foreground transition-colors hover:border-primary/40 placeholder:text-fg-subtle disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
