import { useTranslations } from "next-intl";
import { Waveform } from "@/components/waveform";
import { LanguageSwitcher } from "@/components/language-switcher";

const GITHUB_URL = "https://github.com/akshinmrv/Voxa";
const LICENSE_URL = "https://github.com/akshinmrv/Voxa/blob/main/LICENSE";

export function LandingFooter() {
  const t = useTranslations("Footer");

  return (
    <footer className="mt-auto border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-12 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Waveform bars={5} animated={false} className="h-5" />
            <span className="text-lg font-semibold tracking-tight">Voxa</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{t("tagline")}</p>
          <p className="mt-4 text-xs text-fg-subtle">
            {t("builtBy")} · {t("license")}
          </p>
        </div>

        <div className="flex flex-col items-start gap-4 md:items-end">
          <nav className="flex items-center gap-6 text-sm">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              {t("github")}
            </a>
            <a
              href={LICENSE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              {t("licenseLink")}
            </a>
          </nav>
          <LanguageSwitcher />
        </div>
      </div>
    </footer>
  );
}
