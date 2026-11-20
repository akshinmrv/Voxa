"use client";

import { useMemo } from "react";
import { useLocale, useTranslations } from "next-intl";

/**
 * A language's name from its code: Voxa's own for the ones it lists (Edge's ICU has no
 * Azerbaijani names, and gave "Ru", "Tr"), the browser's for any other, else the fallback
 * (the server's English name, or the code).
 */
export function useLanguageNames() {
  const locale = useLocale();
  const ts = useTranslations("App.studio");
  return useMemo(() => {
    let display: Intl.DisplayNames | null = null;
    try {
      display = new Intl.DisplayNames([locale], { type: "language" });
    } catch {
      /* an old engine */
    }
    return (code: string, fallback: string = code) => {
      if (ts.has(`langNames.${code}`)) return ts(`langNames.${code}` as "langNames.en");
      const shown = display?.of(code);
      const name = shown && shown.toLowerCase() !== code.toLowerCase() ? shown : fallback;
      return name.charAt(0).toLocaleUpperCase(locale) + name.slice(1);
    };
  }, [locale, ts]);
}
