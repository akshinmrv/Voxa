"use client";

import { useSyncExternalStore } from "react";

// The sidebar's width lives on <html data-sidebar>, which CSS reads (globals.css): set before
// the first paint by SIDEBAR_SCRIPT from the last choice, and here when it is toggled. React
// only reads it back, for the toggle's label and the rail's tooltips.

const KEY = "voxa.sidebar";
const NARROW = "(max-width: 1099px)";
const listeners = new Set<() => void>();

function choice(): "collapsed" | "expanded" | null {
  const value = document.documentElement.dataset.sidebar;
  return value === "collapsed" || value === "expanded" ? value : null;
}

function collapsed(): boolean {
  const chosen = choice();
  return chosen ? chosen === "collapsed" : window.matchMedia(NARROW).matches;
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const narrow = window.matchMedia(NARROW);
  narrow.addEventListener("change", onChange);
  return () => {
    listeners.delete(onChange);
    narrow.removeEventListener("change", onChange);
  };
}

/** Whether the sidebar is the icon rail now. */
export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(subscribe, collapsed, () => false);
}

export function toggleSidebar(): void {
  const next = collapsed() ? "expanded" : "collapsed";
  document.documentElement.dataset.sidebar = next;
  try {
    window.localStorage.setItem(KEY, next);
  } catch {
    /* storage blocked: it holds for this visit */
  }
  listeners.forEach((notify) => notify());
}

/** Runs before the first paint: the sidebar opens as it was left. */
export const SIDEBAR_SCRIPT = `try{var s=localStorage.getItem(${JSON.stringify(
  KEY,
)});if(s==="collapsed"||s==="expanded")document.documentElement.dataset.sidebar=s}catch(e){}`;
