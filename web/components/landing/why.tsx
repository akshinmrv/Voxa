import { useTranslations } from "next-intl";
import { Waveform } from "@/components/waveform";

export function Why() {
  const t = useTranslations("Why");

  return (
    <section className="border-y border-border bg-surface-1">
      <div className="mx-auto grid w-full max-w-6xl gap-8 px-6 py-20 md:grid-cols-2 md:items-center">
        <div>
          <p className="type-label text-primary">{t("label")}</p>
          <h2 className="type-h1 mt-3 text-balance">{t("title")}</h2>
          <p className="type-body mt-4 text-pretty text-muted-foreground">
            {t("body")}
          </p>
        </div>
        <div className="flex justify-center md:justify-end">
          <div className="flex h-40 w-full max-w-sm items-center justify-center rounded-lg border border-border bg-background">
            <Waveform bars={28} className="h-16" />
          </div>
        </div>
      </div>
    </section>
  );
}
