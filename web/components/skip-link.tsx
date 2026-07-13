import { useTranslations } from "next-intl";

/** Keyboard skip link — hidden until focused, then jumps to #main-content (a11y §15). */
export function SkipLink() {
  const t = useTranslations("Common");
  return (
    <a
      href="#main-content"
      className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-4 focus-visible:top-4 focus-visible:z-[100] focus-visible:rounded-sm focus-visible:border focus-visible:border-border focus-visible:bg-surface-1 focus-visible:px-4 focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-foreground"
    >
      {t("skipToContent")}
    </a>
  );
}
