"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { AudioLines } from "lucide-react";
import { VOICE_SAMPLES, VOICE_MODEL } from "@/lib/voices";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "./section-header";
import { cn } from "@/lib/utils";

export function Voices() {
  const t = useTranslations("Voices");
  const [active, setActive] = useState(0);
  const current = VOICE_SAMPLES[active];

  return (
    <section id="voices" className="scroll-mt-20 border-y border-border bg-surface-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />

        <div className="mt-8 flex justify-center">
          <Badge variant="brand">
            <AudioLines /> OpenAI · {VOICE_MODEL}
          </Badge>
        </div>

        <div
          role="tablist"
          aria-label={t("title")}
          className="mt-6 flex flex-wrap justify-center gap-2"
        >
          {VOICE_SAMPLES.map((voice, i) => (
            <button
              key={voice.id}
              role="tab"
              type="button"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={cn(
                "rounded-sm border px-3 py-1.5 text-sm font-medium capitalize transition-colors",
                i === active
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-background text-muted-foreground hover:text-foreground",
              )}
            >
              {voice.id}
            </button>
          ))}
        </div>

        <div className="mt-6 rounded-md border border-border bg-background p-5">
          {/* key forces a reload when the selected voice changes */}
          <audio
            key={current.src}
            controls
            preload="none"
            className="w-full"
            src={current.src}
          />
          <p className="mt-4 text-center text-sm italic text-muted-foreground">
            {t("sample")}
          </p>
        </div>
      </div>
    </section>
  );
}
