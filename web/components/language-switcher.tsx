"use client";

import { useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { cn } from "@/lib/utils";

const LABELS: Record<string, string> = { en: "EN", az: "AZ", tr: "TR" };

/** Segmented locale switcher — keeps the current path, swaps the locale prefix. */
export function LanguageSwitcher() {
  const t = useTranslations("Common");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  return (
    <div
      role="group"
      aria-label={t("languageLabel")}
      className="inline-flex items-center rounded-sm border border-border bg-surface-1 p-0.5"
    >
      {routing.locales.map((loc) => {
        const active = loc === locale;
        return (
          <button
            key={loc}
            type="button"
            aria-current={active ? "true" : undefined}
            disabled={isPending}
            onClick={() =>
              startTransition(() => router.replace(pathname, { locale: loc }))
            }
            className={cn(
              "rounded-[4px] px-2 py-1 text-xs font-medium transition-colors",
              active
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {LABELS[loc]}
          </button>
        );
      })}
    </div>
  );
}
