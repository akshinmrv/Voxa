"use client";

import { useTheme } from "next-themes";
import { useLocale, useTranslations } from "next-intl";
import { Command } from "cmdk";
import {
  BookOpen,
  FileVideo,
  FolderOpen,
  Globe,
  Keyboard,
  Languages,
  Monitor,
  Moon,
  PanelLeft,
  Plus,
  Search,
  Sun,
} from "lucide-react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { useDesktop } from "@/lib/desktop";
import { useJobs } from "@/lib/use-jobs";
import { SITE } from "@/lib/site";
import { keyLabel } from "@/lib/shortcuts";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { GithubIcon } from "@/components/icons/github";
import { APP_NAV, SETTINGS_NAV, SYSTEM_NAV } from "@/components/app/nav-items";
import { toggleSidebar } from "./sidebar-state";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", az: "Azərbaycanca", tr: "Türkçe" };
const RECENT = 8;

const itemClass =
  "flex cursor-default select-none items-center gap-2.5 rounded-sm px-2 py-2 text-ui-body text-foreground outline-none data-[selected=true]:bg-surface-2 data-[disabled=true]:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-muted-foreground";

function Item({
  onSelect,
  children,
  shortcut,
  keywords,
}: {
  onSelect: () => void;
  children: React.ReactNode;
  shortcut?: string;
  keywords?: string[];
}) {
  return (
    <Command.Item onSelect={onSelect} keywords={keywords} className={itemClass}>
      {children}
      {shortcut && (
        <span className="ml-auto pl-4 font-mono text-ui-mono text-fg-subtle">{shortcut}</span>
      )}
    </Command.Item>
  );
}

/**
 * Ctrl+K: every page, the console's commands and the latest dubs, by typing a few letters
 * (VOXA_DESIGN_PLAN.md §6.7). cmdk does the filtering and the listbox semantics.
 */
export function CommandPalette({
  open,
  onOpenChange,
  onShortcuts,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onShortcuts: () => void;
}) {
  const t = useTranslations("App");
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const { setTheme } = useTheme();
  const desktop = useDesktop();
  const jobs = useJobs().data?.jobs ?? [];
  // The server lists them oldest first.
  const recent = jobs.slice(-RECENT).reverse();

  const run = (action: () => void) => () => {
    onOpenChange(false);
    action();
  };
  const external = (url: string) => run(() => window.open(url, "_blank", "noopener,noreferrer"));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        aria-describedby={undefined}
        className="top-[16%] max-w-xl translate-y-0 gap-0 overflow-hidden p-0"
      >
        <DialogTitle className="sr-only">{t("shell.palette.title")}</DialogTitle>
        <Command
          loop
          className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-ui-label [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:text-muted-foreground"
        >
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <Command.Input
              autoFocus
              placeholder={t("shell.palette.placeholder")}
              className="h-11 flex-1 bg-transparent text-ui-body text-foreground outline-none placeholder:text-fg-subtle"
            />
          </div>
          <Command.List className="max-h-[min(24rem,60vh)] overflow-y-auto p-1.5">
            <Command.Empty className="py-8 text-center text-ui-small text-muted-foreground">
              {t("shell.palette.empty")}
            </Command.Empty>

            <Command.Group heading={t("shell.palette.goTo")}>
              {APP_NAV.map((item, i) => {
                const Icon = item.icon;
                return (
                  <Item
                    key={item.href}
                    onSelect={run(() => router.push(item.href))}
                    shortcut={desktop ? keyLabel(["Mod", String(i + 1)]) : undefined}
                  >
                    <Icon /> {t(`nav.${item.key}`)}
                  </Item>
                );
              })}
              <Item
                onSelect={run(() => router.push(SETTINGS_NAV.href))}
                shortcut={keyLabel(["Mod", ","])}
              >
                <SETTINGS_NAV.icon /> {t("nav.settings")}
              </Item>
              <Item onSelect={run(() => router.push(SYSTEM_NAV.href))}>
                <SYSTEM_NAV.icon /> {t("nav.system")}
              </Item>
            </Command.Group>

            <Command.Group heading={t("shell.palette.actions")}>
              <Item
                onSelect={run(() => router.push("/app"))}
                shortcut={desktop ? keyLabel(["Mod", "N"]) : undefined}
              >
                <Plus /> {t("shell.palette.newDub")}
              </Item>
              <Item onSelect={run(() => setTheme("dark"))}>
                <Moon /> {t("shell.palette.themeDark")}
              </Item>
              <Item onSelect={run(() => setTheme("light"))}>
                <Sun /> {t("shell.palette.themeLight")}
              </Item>
              <Item onSelect={run(() => setTheme("system"))}>
                <Monitor /> {t("shell.palette.themeSystem")}
              </Item>
              {routing.locales
                .filter((code) => code !== locale)
                .map((code) => (
                  <Item
                    key={code}
                    keywords={["language", "dil", code]}
                    // Keep the page's query (a dub's ?id=) across the switch.
                    onSelect={run(() =>
                      router.replace(`${pathname}${window.location.search}`, { locale: code }),
                    )}
                  >
                    <Languages /> {t("shell.palette.language", { name: LANGUAGE_NAMES[code] })}
                  </Item>
                ))}
              <Item onSelect={run(toggleSidebar)} shortcut={keyLabel(["Mod", "B"])}>
                <PanelLeft /> {t("shell.palette.sidebar")}
              </Item>
              <Item onSelect={run(onShortcuts)} shortcut="?">
                <Keyboard /> {t("shell.palette.shortcuts")}
              </Item>
              {desktop && (
                <Item onSelect={run(() => void desktop.open_logs())}>
                  <FolderOpen /> {t("shell.palette.openLogs")}
                </Item>
              )}
            </Command.Group>

            {recent.length > 0 && (
              <Command.Group heading={t("shell.palette.recent")}>
                {recent.map((job) => (
                  <Item
                    key={job.id}
                    keywords={[job.config.targetLang, job.id]}
                    onSelect={run(() =>
                      router.push({ pathname: "/app/jobs/view", query: { id: job.id } }),
                    )}
                  >
                    <FileVideo />
                    <span className="min-w-0 flex-1 truncate">{job.fileName}</span>
                    <span className="font-mono text-ui-mono text-fg-subtle">
                      {job.config.targetLang}
                    </span>
                  </Item>
                ))}
              </Command.Group>
            )}

            <Command.Group heading={t("shell.palette.help")}>
              <Item onSelect={external(`${SITE.repo}#readme`)}>
                <BookOpen /> {t("shell.palette.docs")}
              </Item>
              <Item onSelect={external(SITE.url)}>
                <Globe /> {t("shell.palette.website")}
              </Item>
              <Item onSelect={external(SITE.repo)}>
                <GithubIcon /> {t("shell.palette.github")}
              </Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
