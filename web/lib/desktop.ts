"use client";

import { useSyncExternalStore } from "react";

/**
 * What Voxa Studio's window offers the console (voxa_studio.StudioApi, through pywebview's
 * js_api). In a browser — `voxa serve`, Docker, another machine — there is none, and every
 * desktop-only control stays hidden: the console works the same without it.
 */
export interface VoxaDesktop {
  /** Paint the window's title bar for the console's theme. */
  set_chrome(theme: "dark" | "light"): Promise<boolean>;
  /** Open the folder with Voxa's logs (.voxa_serve) in Explorer. */
  open_logs(): Promise<boolean>;
  app_info(): Promise<{ shell: string | null; renderer: string | null; os: string }>;
}

declare global {
  interface Window {
    pywebview?: { api?: Partial<VoxaDesktop> };
  }
}

function current(): VoxaDesktop | null {
  const api = window.pywebview?.api;
  return api && typeof api.set_chrome === "function" ? (api as VoxaDesktop) : null;
}

// pywebview injects its API once the page has loaded, and says so with this event.
function subscribe(onChange: () => void) {
  window.addEventListener("pywebviewready", onChange);
  return () => window.removeEventListener("pywebviewready", onChange);
}

/** The window's API in Voxa Studio, null anywhere else. */
export function useDesktop(): VoxaDesktop | null {
  return useSyncExternalStore(subscribe, current, () => null);
}
