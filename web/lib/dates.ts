"use client";

import { useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";

export type Dates = {
  /** 14:20, or 2:20 PM. */
  time(date: Date): string;
  /** 16 Nov; with the year, 16 Nov 2025. */
  day(date: Date, withYear?: boolean): string;
  /** The day, the year and the time. */
  dateTime(date: Date): string;
};

/**
 * Dates as the console's language writes them. Edge's ICU, which WebView2 shares, has no
 * Azerbaijani month names and writes "2026 M11 16"; where a language's months are missing so,
 * Voxa's own names stand in (Common.months).
 */
export function useDates(): Dates {
  const locale = useLocale();
  const t = useTranslations("Common");
  return useMemo(() => {
    const months = t.raw("months") as string[];
    const time = new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit" });
    const probe = new Intl.DateTimeFormat(locale, { month: "short" }).format(new Date(2026, 10, 1));
    const own = /M\d/.test(probe);
    const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
    const dayYear = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    const full = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
    const ownDay = (date: Date, withYear: boolean) =>
      `${date.getDate()} ${months[date.getMonth()]}${withYear ? ` ${date.getFullYear()}` : ""}`;
    return {
      time: (date) => time.format(date),
      day: (date, withYear = false) =>
        own ? ownDay(date, withYear) : (withYear ? dayYear : day).format(date),
      dateTime: (date) => (own ? `${ownDay(date, true)}, ${time.format(date)}` : full.format(date)),
    };
  }, [locale, t]);
}
