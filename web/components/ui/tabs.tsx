"use client";

import * as React from "react";
import * as T from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = T.Root;

function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return (
    <T.List
      className={cn("flex items-center gap-1 border-b border-border", className)}
      {...props}
    />
  );
}

/** Underlined, as in a desktop app: the active tab carries a 2 px brand line, not a fill. */
function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "relative -mb-px inline-flex h-9 items-center gap-2 border-b-2 border-transparent px-3 text-ui-body font-medium text-muted-foreground transition-colors duration-(--dur-1) hover:text-foreground disabled:pointer-events-none disabled:opacity-50 data-[state=active]:border-primary data-[state=active]:text-foreground [&_svg]:size-4",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof T.Content>) {
  return <T.Content className={cn("pt-4 outline-none", className)} {...props} />;
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
