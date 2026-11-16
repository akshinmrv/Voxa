"use client";

import * as React from "react";
import * as A from "@radix-ui/react-alert-dialog";
import { cn } from "@/lib/utils";
import { buttonVariants } from "./button";
import { dialogOverlay, dialogPanel } from "./dialog";

/**
 * For what can't be undone: deleting, resetting, stopping a dub. Its title names the act, its
 * text says what follows, and the confirming button is named for the act ("Delete", never
 * "OK"). Radix puts the focus on Cancel when it opens, so Enter doesn't confirm by accident.
 */
const AlertDialog = A.Root;
const AlertDialogTrigger = A.Trigger;

function AlertDialogContent({ className, ...props }: React.ComponentProps<typeof A.Content>) {
  return (
    <A.Portal>
      <A.Overlay className={dialogOverlay} />
      <A.Content className={cn(dialogPanel, "max-w-md", className)} {...props} />
    </A.Portal>
  );
}

function AlertDialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("grid gap-1.5", className)} {...props} />;
}

function AlertDialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}

function AlertDialogTitle({ className, ...props }: React.ComponentProps<typeof A.Title>) {
  return <A.Title className={cn("text-ui-title", className)} {...props} />;
}

function AlertDialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof A.Description>) {
  return <A.Description className={cn("text-muted-foreground", className)} {...props} />;
}

function AlertDialogCancel({ className, ...props }: React.ComponentProps<typeof A.Cancel>) {
  return (
    <A.Cancel className={cn(buttonVariants({ variant: "secondary", size: "sm" }), className)} {...props} />
  );
}

function AlertDialogAction({
  className,
  destructive,
  ...props
}: React.ComponentProps<typeof A.Action> & { destructive?: boolean }) {
  return (
    <A.Action
      className={cn(
        buttonVariants({ variant: destructive ? "destructive" : "primary", size: "sm" }),
        className,
      )}
      {...props}
    />
  );
}

export {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
  AlertDialogAction,
};
