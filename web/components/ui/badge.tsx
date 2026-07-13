import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Status badge — pill shape, semantic tint + text (color is never the only signal;
 * pair with an icon or label at the call site). DESIGN_SYSTEM.md §8.5, §15.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        neutral: "border-border bg-secondary text-secondary-foreground",
        brand: "border-brand/25 bg-brand/15 text-brand",
        success: "border-success/25 bg-success/15 text-success",
        warning: "border-warning/25 bg-warning/15 text-warning",
        danger: "border-danger/25 bg-danger/15 text-danger",
        info: "border-info/25 bg-info/15 text-info",
        outline: "border-border bg-transparent text-foreground",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
