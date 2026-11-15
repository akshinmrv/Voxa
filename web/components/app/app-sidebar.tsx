"use client";

import { useTranslations } from "next-intl";
import { ArrowLeft, ArrowUpCircle, BookOpen } from "lucide-react";
import { Link, usePathname } from "@/i18n/navigation";
import { Waveform } from "@/components/waveform";
import { APP_NAV } from "./nav-items";
import { cn } from "@/lib/utils";
import { IS_CONSOLE, SITE } from "@/lib/site";
import { useUpdateStatus } from "@/lib/use-update";

const DOCS_URL = "https://github.com/akshinmrv/Voxa#readme";

function isActive(pathname: string, href: string, exact?: boolean) {
  return exact ? pathname === href : pathname.startsWith(href);
}

/** Vertical app navigation — desktop only (lg+). Mobile uses the topbar nav. */
export function AppSidebar() {
  const t = useTranslations("App.nav");
  const tu = useTranslations("App.update");
  const pathname = usePathname();
  const update = useUpdateStatus().data;

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface-1 lg:flex">
      <div className="flex h-16 items-center gap-2.5 border-b border-border px-5">
        <Link href="/app" className="flex items-center gap-2.5" aria-label="Voxa">
          <Waveform bars={5} className="h-5" />
          <span className="text-lg font-semibold tracking-tight">Voxa</span>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {APP_NAV.map((item) => {
          const active = isActive(pathname, item.href, item.exact);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-sm px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {t(item.key)}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <a
          href={DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 rounded-sm px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <BookOpen className="size-4" />
          {t("docs")}
        </a>
        {IS_CONSOLE ? (
          <a
            href={SITE.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-sm px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            {t("backToSite")}
          </a>
        ) : (
          <Link
            href="/"
            className="flex items-center gap-3 rounded-sm px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            {t("backToSite")}
          </Link>
        )}
        {update && (
          <p className="flex items-center gap-2 px-3 pt-2 text-xs text-muted-foreground">
            <span className="tabular-nums">{tu("version", { version: update.current })}</span>
            {update.newer && update.latest && update.notes && (
              <a
                href={update.notes}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <ArrowUpCircle className="size-3.5" />
                {tu("newer", { latest: update.latest })}
              </a>
            )}
          </p>
        )}
      </div>
    </aside>
  );
}
