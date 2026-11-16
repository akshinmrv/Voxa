import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 aria-busy:cursor-progress [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-foreground hover:bg-primary/90",
        secondary:
          "bg-secondary text-secondary-foreground border border-border hover:bg-surface-2/70",
        outline:
          "border border-border bg-transparent text-foreground hover:bg-accent hover:text-accent-foreground",
        ghost:
          "bg-transparent text-foreground hover:bg-accent hover:text-accent-foreground",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        link: "text-primary underline-offset-4 hover:underline bg-transparent",
      },
      // The desktop app's controls are 28-32 px (xs, sm, icon-sm); default and lg are the
      // landing's and the console's of today, kept until each screen is redone.
      size: {
        xs: "h-7 px-2.5 text-xs",
        sm: "h-8 px-3 text-sm",
        default: "h-10 px-4",
        lg: "h-11 px-6 text-base",
        icon: "size-10",
        "icon-sm": "size-8",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the child element (e.g. an <a>) while keeping button styles. */
  asChild?: boolean;
  /** Working on it: a spinner in place of its icon, and it can't be pressed again. */
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    const busy = loading && !asChild;
    return (
      <Comp
        ref={ref}
        className={cn(
          buttonVariants({ variant, size, className }),
          // The spinner stands in for the button's own icon rather than sitting beside it.
          busy && "[&>svg:not([data-spinner])]:hidden",
        )}
        aria-busy={loading || undefined}
        {...props}
        disabled={asChild ? props.disabled : props.disabled || loading}
      >
        {asChild ? (
          children
        ) : (
          <>
            {busy && <Loader2 data-spinner className="animate-spin" aria-hidden />}
            {children}
          </>
        )}
      </Comp>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
