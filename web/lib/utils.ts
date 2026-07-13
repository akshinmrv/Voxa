import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names, resolving conflicts (last one wins).
 * Used by every Voxa primitive so callers can override styles cleanly.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
