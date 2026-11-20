"use client";

import { useEffect, useState } from "react";
import { useRouter as useNextRouter } from "next/navigation";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export type LeaveGuard = {
  /** Where a link would have taken the page, held while it asks. */
  to: string | null;
  /** Ask before going somewhere the page sends you itself (another language, say). */
  ask: (url: string) => void;
  stay: () => void;
  /** Go after all, forgetting what wasn't saved first. */
  leave: (forget?: () => void) => void;
};

/**
 * Not losing what was typed: while `dirty`, a link to another page of the console asks first,
 * and closing or reloading the tab gets the browser's own question.
 */
export function useLeaveGuard(dirty: boolean): LeaveGuard {
  const nextRouter = useNextRouter();
  const [to, setTo] = useState<string | null>(null);

  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    const onClick = (event: MouseEvent) => {
      const link = (event.target as HTMLElement | null)?.closest?.("a[href]");
      if (!(link instanceof HTMLAnchorElement) || event.defaultPrevented) return;
      if (link.target === "_blank" || link.hasAttribute("download") || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      event.preventDefault();
      event.stopPropagation();
      setTo(url.pathname + url.search);
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [dirty]);

  return {
    to,
    ask: setTo,
    stay: () => setTo(null),
    leave: (forget) => {
      const next = to;
      forget?.();
      setTo(null);
      if (next) nextRouter.push(next);
    },
  };
}

/** The question a guarded page asks before it is left. */
export function LeaveDialog({
  guard,
  title,
  body,
  stayLabel,
  leaveLabel,
  onForget,
}: {
  guard: LeaveGuard;
  title: string;
  body: string;
  stayLabel: string;
  leaveLabel: string;
  onForget?: () => void;
}) {
  return (
    <AlertDialog open={guard.to !== null} onOpenChange={(open) => !open && guard.stay()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{body}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{stayLabel}</AlertDialogCancel>
          <AlertDialogAction destructive onClick={() => guard.leave(onForget)}>
            {leaveLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
