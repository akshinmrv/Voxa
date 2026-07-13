import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { SITE } from "@/lib/site";
import { Waveform } from "@/components/waveform";
import { Button } from "@/components/ui/button";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { GithubIcon } from "@/components/icons/github";

/**
 * Shown in place of the operator app on a public deploy (IS_PUBLIC). Dubbing only
 * ever runs on the user's own machine, so this points them at the local install.
 */
export function LocalOnlyNotice() {
  const t = useTranslations("App.localOnly");

  return (
    <main
      id="main-content"
      className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center px-6 py-24 text-center"
    >
      <Waveform bars={12} className="h-10" />
      <h1 className="type-h1 mt-8">{t("title")}</h1>
      <p className="type-body mt-4 text-muted-foreground">{t("body")}</p>

      <div className="mt-8 w-full space-y-3 text-left">
        <TerminalBlock label={t("installLabel")} command={t("install")} />
        <TerminalBlock label={t("serveLabel")} command={t("serve")} />
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button asChild variant="secondary">
          <Link href="/">
            <ArrowLeft /> {t("backHome")}
          </Link>
        </Button>
        <Button asChild>
          <a href={SITE.repo} target="_blank" rel="noopener noreferrer">
            <GithubIcon /> {t("viewGithub")}
          </a>
        </Button>
      </div>
    </main>
  );
}
