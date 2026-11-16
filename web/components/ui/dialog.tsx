"use client";

import * as React from "react";
import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = D.Root;
const DialogTrigger = D.Trigger;
const DialogClose = D.Close;

const overlay =
  "fixed inset-0 z-50 bg-scrim data-[state=open]:animate-voxa-fade-in data-[state=closed]:animate-voxa-fade-out";

/** A centred panel; the shared class is exported for AlertDialog, which looks the same. */
const dialogPanel =
  "fixed left-1/2 top-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 rounded-lg border border-border bg-surface-3 p-6 text-ui-body text-foreground shadow-overlay outline-none data-[state=open]:animate-voxa-in data-[state=closed]:animate-voxa-out";

function DialogContent({
  className,
  children,
  closeLabel,
  ...props
}: React.ComponentProps<typeof D.Content> & {
  /** Shows a ✕ in the corner, named this for screen readers. */
  closeLabel?: string;
}) {
  return (
    <D.Portal>
      <D.Overlay className={overlay} />
      <D.Content className={cn(dialogPanel, className)} {...props}>
        {children}
        {closeLabel && (
          <D.Close
            aria-label={closeLabel}
            className="absolute right-3 top-3 inline-flex size-8 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-2 hover:text-foreground [&_svg]:size-4"
          >
            <X />
          </D.Close>
        )}
      </D.Content>
    </D.Portal>
  );
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("grid gap-1.5 pr-8", className)} {...props} />;
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}

function DialogTitle({ className, ...props }: React.ComponentProps<typeof D.Title>) {
  return <D.Title className={cn("text-ui-title", className)} {...props} />;
}

function DialogDescription({ className, ...props }: React.ComponentProps<typeof D.Description>) {
  return <D.Description className={cn("text-muted-foreground", className)} {...props} />;
}

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  dialogPanel,
  overlay as dialogOverlay,
};
