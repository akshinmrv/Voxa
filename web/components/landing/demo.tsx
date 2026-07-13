"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Captions } from "lucide-react";
import { DEMOS } from "@/lib/demos";
import { Waveform } from "@/components/waveform";
import { SectionHeader } from "./section-header";
import { cn } from "@/lib/utils";

export function Demo() {
  const t = useTranslations("Demo");
  const [active, setActive] = useState(0);

  return (
    <section id="demo" className="scroll-mt-20">
      <div className="mx-auto w-full max-w-4xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />

        {DEMOS.length > 0 ? (
          <>
            <div
              role="tablist"
              aria-label={t("title")}
              className="mt-10 flex flex-wrap justify-center gap-2"
            >
              {DEMOS.map((clip, i) => (
                <button
                  key={clip.code}
                  role="tab"
                  type="button"
                  aria-selected={i === active}
                  onClick={() => setActive(i)}
                  className={cn(
                    "rounded-sm border px-3 py-1.5 text-sm font-medium transition-colors",
                    i === active
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-border bg-surface-1 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t(`langs.${clip.code}`)}
                </button>
              ))}
            </div>

            <div className="mt-6 overflow-hidden rounded-lg border border-border bg-surface-1">
              {/* key forces a reload when the selected clip changes */}
              <video
                key={DEMOS[active].src}
                controls
                preload="metadata"
                playsInline
                className="aspect-video w-full bg-black"
                src={DEMOS[active].src}
              />
            </div>
          </>
        ) : (
          <div className="mt-12 overflow-hidden rounded-lg border border-border bg-surface-1">
            <div className="flex aspect-video w-full flex-col items-center justify-center gap-4 bg-background">
              <Waveform bars={20} animated={false} className="h-12" />
              <p className="text-sm text-muted-foreground">{t("placeholder")}</p>
            </div>
          </div>
        )}

        <p className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Captions className="size-3.5" />
          {t("captionsNote")}
        </p>
      </div>
    </section>
  );
}
