import { useTranslations } from "next-intl";
import { Captions } from "lucide-react";
import { DEMO_VIDEO, DEMO_POSTER } from "@/lib/site";
import { Waveform } from "@/components/waveform";
import { SectionHeader } from "./section-header";

export function Demo() {
  const t = useTranslations("Demo");

  return (
    <section id="demo" className="scroll-mt-20">
      <div className="mx-auto w-full max-w-4xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />

        <div className="mt-12 overflow-hidden rounded-lg border border-border bg-surface-1">
          {DEMO_VIDEO ? (
            // No autoplay — respects prefers-reduced-motion and gives users control.
            <video
              controls
              preload="metadata"
              playsInline
              poster={DEMO_POSTER || undefined}
              className="aspect-video w-full bg-black"
              src={DEMO_VIDEO}
            />
          ) : (
            <div className="flex aspect-video w-full flex-col items-center justify-center gap-4 bg-background">
              <Waveform bars={20} animated={false} className="h-12" />
              <p className="text-sm text-muted-foreground">{t("placeholder")}</p>
            </div>
          )}
        </div>

        <p className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Captions className="size-3.5" />
          {t("captionsNote")}
        </p>
      </div>
    </section>
  );
}
