import { AudioLines, Boxes, Clapperboard, ListVideo, Settings, type LucideIcon } from "lucide-react";

export type AppNavItem = {
  href: string;
  icon: LucideIcon;
  /** key under the App.nav namespace */
  key: "newJob" | "jobs" | "voices" | "models" | "settings";
  /** exact match for active state (only the index route) */
  exact?: boolean;
};

/** Studio, Dubs, Voices, Engines: Ctrl+1…4 in that order. Their URLs predate the names. */
export const APP_NAV: AppNavItem[] = [
  { href: "/app", icon: Clapperboard, key: "newJob", exact: true },
  { href: "/app/jobs", icon: ListVideo, key: "jobs" },
  { href: "/app/voices", icon: AudioLines, key: "voices" },
  { href: "/app/models", icon: Boxes, key: "models" },
];

export const SETTINGS_NAV: AppNavItem = { href: "/app/settings", icon: Settings, key: "settings" };

export function isActive(pathname: string, item: AppNavItem): boolean {
  // The console is exported with trailing slashes: /app/ is /app.
  const path = pathname.replace(/\/+$/, "") || "/";
  return item.exact ? path === item.href : path === item.href || path.startsWith(`${item.href}/`);
}

/** The section a page belongs to, for the header's title. */
export function sectionOf(pathname: string): AppNavItem | undefined {
  return [...APP_NAV, SETTINGS_NAV].find((item) => isActive(pathname, item));
}
