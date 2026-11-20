"use client";

import { useSyncExternalStore } from "react";

// Short notes in the corner: what an action did, or why it didn't, or that a dub needs you
// (VOXA_DESIGN_PLAN.md §7.5). One list for the whole console, so a note outlives the menu or
// dialog that made it.

export type ToastTone = "info" | "success" | "warning" | "error";

export type Toast = {
  id: number;
  text: string;
  tone: ToastTone;
  /** A way to act on it: open the dub it is about, say. */
  action?: { label: string; href: string };
};

const SHOWN = 3;
const EMPTY: Toast[] = [];
let toasts: Toast[] = EMPTY;
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

/**
 * Say it for a few seconds; an error stays a little longer. `sticky` keeps it until it is
 * closed: a dub that failed while you looked elsewhere shouldn't vanish before you read why.
 */
export function toast(
  text: string,
  tone: ToastTone = "info",
  options: { action?: Toast["action"]; sticky?: boolean } = {},
) {
  const id = nextId++;
  toasts = [...toasts, { id, text, tone, action: options.action }].slice(-SHOWN);
  emit();
  if (!options.sticky) setTimeout(() => dismissToast(id), tone === "error" ? 9000 : 6000);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useToasts(): Toast[] {
  return useSyncExternalStore(
    subscribe,
    () => toasts,
    () => EMPTY,
  );
}
