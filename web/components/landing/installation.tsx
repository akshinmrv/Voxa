import { useTranslations } from "next-intl";
import { Download, Info, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { DOWNLOAD_PATH } from "@/lib/site";
import { SectionHeader } from "./section-header";

export function Installation() {
  const t = useTranslations("Install");

  return (
    <section id="install" className="scroll-mt-20 border-y border-border bg-surface-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-24">
        <SectionHeader label={t("label")} title={t("title")} subtitle={t("subtitle")} />

        <div className="mt-12 rounded-lg border border-border bg-background p-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h3 className="type-h3">{t("setupTitle")}</h3>
              <p className="type-small mt-2 text-pretty text-muted-foreground">{t("setupBody")}</p>
            </div>
            <Button asChild size="lg" className="shrink-0">
              <a href={DOWNLOAD_PATH}>
                <Download />
                {t("setupButton")}
              </a>
            </Button>
          </div>
          <p className="type-small mt-4 text-muted-foreground">{t("setupSize")}</p>
          <div className="mt-4 flex gap-3 rounded-md border border-border bg-surface-1 p-4">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <p className="type-small text-muted-foreground">{t("setupUnsigned")}</p>
          </div>
        </div>

        <h3 className="type-label mt-12 text-muted-foreground">{t("oneLine")}</h3>
        <div className="mt-4 space-y-4">
          <TerminalBlock label={t("windowsLabel")} command={t("windows")} />
          <TerminalBlock label={t("unixLabel")} command={t("unix")} />
          <TerminalBlock label={t("runLabel")} command={t("run")} />
        </div>
        <div className="mt-6 flex gap-3 rounded-md border border-primary/25 bg-primary/10 p-4">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">{t("note")}</p>
        </div>
      </div>
    </section>
  );
}
