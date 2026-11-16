"use client";

import { useTranslations } from "next-intl";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Link, usePathname } from "@/i18n/navigation";
import { Waveform } from "@/components/waveform";
import { Tooltip } from "@/components/ui/tooltip";
import { APP_NAV, SETTINGS_NAV, isActive, type AppNavItem } from "@/components/app/nav-items";
import { countJobs, useJobs } from "@/lib/use-jobs";
import { keyLabel } from "@/lib/shortcuts";
import { cn } from "@/lib/utils";
import { toggleSidebar, useSidebarCollapsed } from "./sidebar-state";

function NavLink({
  item,
  active,
  collapsed,
  label,
  shortcut,
  badge,
  attention,
  onNavigate,
}: {
  item: AppNavItem;
  active: boolean;
  collapsed: boolean;
  label: string;
  shortcut?: string;
  /** A count beside the label: dubs going. */
  badge?: number;
  /** A dot: something waits for the user (a translation to check). */
  attention?: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? label : undefined}
      className={cn(
        "relative flex h-9 items-center gap-3 rounded-sm px-3 text-ui-body font-medium transition-colors duration-(--dur-1)",
        active
          ? "bg-surface-2 text-foreground before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-primary"
          : "text-muted-foreground hover:bg-surface-2/60 hover:text-foreground",
      )}
    >
      <span className="relative flex shrink-0">
        <Icon className={cn("size-[18px]", active && "text-primary")} aria-hidden />
        {(attention || (collapsed && !!badge)) && (
          <span
            aria-hidden
            className={cn(
              "absolute -right-1 -top-1 size-2 rounded-full ring-2 ring-surface-0",
              attention ? "bg-warning" : "bg-primary",
            )}
          />
        )}
      </span>
      <span className="voxa-sidebar-label min-w-0 flex-1 truncate">{label}</span>
      {!!badge && (
        <span className="voxa-sidebar-label rounded-full bg-brand-tint px-1.5 font-mono text-ui-mono tabular text-primary">
          {badge}
        </span>
      )}
    </Link>
  );
  return collapsed ? (
    <Tooltip label={label} shortcut={shortcut} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

/** The app's navigation, from md up; below that the header's menu holds it (MobileNav). */
export function Sidebar() {
  const t = useTranslations("App");
  const pathname = usePathname();
  const collapsed = useSidebarCollapsed();
  const count = countJobs(useJobs().data?.jobs);
  const going = count.running + count.queued;

  return (
    <aside
      aria-label={t("shell.nav")}
      className="voxa-sidebar hidden shrink-0 flex-col border-r border-border bg-surface-0 md:flex"
    >
      <div className="flex h-13 shrink-0 items-center px-[19px]">
        <Link href="/app" className="flex items-center gap-2.5" aria-label="Voxa">
          <Waveform bars={4} animated={false} className="h-[18px]" />
          <span className="voxa-sidebar-label text-ui-section tracking-tight">Voxa</span>
        </Link>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {APP_NAV.map((item, i) => (
          <NavLink
            key={item.href}
            item={item}
            active={isActive(pathname, item)}
            collapsed={collapsed}
            label={t(`nav.${item.key}`)}
            shortcut={keyLabel(["Mod", String(i + 1)])}
            badge={item.key === "jobs" ? going : undefined}
            attention={item.key === "jobs" && count.review > 0}
          />
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-border px-2 py-2">
        <NavLink
          item={SETTINGS_NAV}
          active={isActive(pathname, SETTINGS_NAV)}
          collapsed={collapsed}
          label={t("nav.settings")}
          shortcut={keyLabel(["Mod", ","])}
        />
        <Tooltip
          label={collapsed ? t("shell.expand") : t("shell.collapse")}
          shortcut={keyLabel(["Mod", "B"])}
          side="right"
        >
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label={collapsed ? t("shell.expand") : t("shell.collapse")}
            aria-expanded={!collapsed}
            className="flex h-9 w-full items-center gap-3 rounded-sm px-3 text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-2/60 hover:text-foreground"
          >
            {collapsed ? (
              <PanelLeftOpen className="size-[18px]" aria-hidden />
            ) : (
              <PanelLeftClose className="size-[18px]" aria-hidden />
            )}
          </button>
        </Tooltip>
      </div>
    </aside>
  );
}

/** The same links in the phone-sized menu (no rail, no tooltips). */
export function NavList({ onNavigate }: { onNavigate: () => void }) {
  const t = useTranslations("App");
  const pathname = usePathname();
  return (
    <nav aria-label={t("shell.nav")} className="space-y-0.5">
      {[...APP_NAV, SETTINGS_NAV].map((item) => (
        <NavLink
          key={item.href}
          item={item}
          active={isActive(pathname, item)}
          collapsed={false}
          label={t(`nav.${item.key}`)}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  );
}
