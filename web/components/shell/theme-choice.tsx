"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { useTranslations } from "next-intl";
import { Monitor, Moon, Sun } from "lucide-react";
import { SegmentedControl } from "@/components/ui/segmented";

const noSubscribe = () => () => {};

/**
 * Dark, light, or whatever the system is set to. The page is built without knowing the
 * stored theme, so the choice shows once the page is live, never a wrong one first.
 */
export function ThemeChoice({ id }: { id?: string }) {
  const t = useTranslations("App.shell.theme");
  const { theme, setTheme } = useTheme();
  const live = useSyncExternalStore(noSubscribe, () => true, () => false);
  const value = live && (theme === "light" || theme === "system") ? theme : "dark";

  return (
    <SegmentedControl
      aria-labelledby={id}
      value={live ? value : ("" as "dark")}
      onValueChange={setTheme}
      items={[
        { value: "dark", label: t("dark"), icon: <Moon /> },
        { value: "light", label: t("light"), icon: <Sun /> },
        { value: "system", label: t("system"), icon: <Monitor /> },
      ]}
    />
  );
}
