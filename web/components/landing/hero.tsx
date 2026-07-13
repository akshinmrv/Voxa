import { useTranslations } from "next-intl";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Waveform } from "@/components/waveform";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { GithubIcon } from "@/components/icons/github";

const GITHUB_URL = "https://github.com/akshinmrv/Voxa";

export function Hero() {
  const t = useTranslations("Hero");

  return (
    <section className="relative overflow-hidden">
      <div className="mx-auto w-full max-w-6xl px-6 py-24 sm:py-32">
        <div className="mx-auto max-w-3xl text-center">
          <Badge variant="brand" className="mb-6">
            {t("badge")}
          </Badge>
          <h1 className="type-display text-balance">{t("title")}</h1>
          <p className="type-body mx-auto mt-6 max-w-2xl text-pretty text-muted-foreground">
            {t("subtitle")}
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button asChild size="lg">
              <a href="#install">
                {t("ctaPrimary")}
                <ArrowRight />
              </a>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
                <GithubIcon />
                {t("ctaSecondary")}
              </a>
            </Button>
          </div>
        </div>

        <div className="mx-auto mt-16 max-w-2xl">
          <div className="mb-6 flex justify-center">
            <Waveform bars={24} className="h-10" />
          </div>
          <TerminalBlock command={t("command")} label={t("terminalLabel")} />
        </div>
      </div>
    </section>
  );
}
