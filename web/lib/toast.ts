"use client";

import { useSyncExternalStore } from "react";

// Short notes in the corner: what an action did, or why it didn't (VOXA_DESIGN_PLAN.md §7.6).
// One list for the whole console, so a note outlives the menu or dialog that made it.

export type Toast = { id: number; text: string; tone: "info" | "error" };

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

/** Say it for a few seconds; an error stays a little longer. */
export function toast(text: string, tone: Toast["tone"] = "info") {
  const id = nextId++;
  toasts = [...toasts, { id, text, tone }].slice(-SHOWN);
  emit();
  setTimeout(() => dismissToast(id), tone === "error" ? 9000 : 6000);
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
