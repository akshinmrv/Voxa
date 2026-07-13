import { FilePlus2, ListChecks, Boxes, Settings, type LucideIcon } from "lucide-react";

export type AppNavItem = {
  href: string;
  icon: LucideIcon;
  /** key under the App.nav namespace */
  key: "newJob" | "jobs" | "models" | "settings";
  /** exact match for active state (only the index route) */
  exact?: boolean;
};

export const APP_NAV: AppNavItem[] = [
  { href: "/app", icon: FilePlus2, key: "newJob", exact: true },
  { href: "/app/jobs", icon: ListChecks, key: "jobs" },
  { href: "/app/models", icon: Boxes, key: "models" },
  { href: "/app/settings", icon: Settings, key: "settings" },
];
