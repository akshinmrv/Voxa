import { useTranslations } from "next-intl";
import { Info } from "lucide-react";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { SectionHeader } from "./section-header";

export function Installation() {
  const t = useTranslations("Install");

  return (
    <section id="install" className="scroll-mt-20 border-y border-border bg-surface-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />
        <div className="mt-12 space-y-4">
          <TerminalBlock label={t("cloneLabel")} command={t("clone")} />
          <TerminalBlock label={t("installLabel")} command={t("install")} />
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
