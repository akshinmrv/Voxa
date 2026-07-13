"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Waveform } from "@/components/waveform";
import { APP_NAV } from "./nav-items";
import { cn } from "@/lib/utils";

function isActive(pathname: string, href: string, exact?: boolean) {
  return exact ? pathname === href : pathname.startsWith(href);
}

/** Sticky app top bar. Holds the mobile nav (lg:hidden) plus locale + theme. */
export function AppTopbar() {
  const t = useTranslations("App.nav");
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="flex h-16 items-center justify-between gap-4 px-5">
        <div className="flex min-w-0 items-center gap-4">
          <Link
            href="/app"
            className="flex items-center gap-2 lg:hidden"
            aria-label="Voxa"
          >
            <Waveform bars={4} className="h-4" />
            <span className="font-semibold tracking-tight">Voxa</span>
          </Link>
          <nav className="flex items-center gap-1 overflow-x-auto lg:hidden">
            {APP_NAV.map((item) => {
              const active = isActive(pathname, item.href, item.exact);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "whitespace-nowrap rounded-sm px-2.5 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t(item.key)}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
