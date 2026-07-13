import { useTranslations } from "next-intl";
import {
  Target,
  AudioLines,
  Languages,
  Gauge,
  Server,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { SectionHeader } from "./section-header";

const ICONS: Record<string, LucideIcon> = {
  target: Target,
  "audio-lines": AudioLines,
  languages: Languages,
  gauge: Gauge,
  server: Server,
  "refresh-cw": RefreshCw,
};

type FeatureItem = { icon: string; title: string; body: string };

export function Features() {
  const t = useTranslations("Features");
  const items = t.raw("items") as FeatureItem[];

  return (
    <section id="features" className="scroll-mt-20">
      <div className="mx-auto w-full max-w-6xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => {
            const Icon = ICONS[item.icon] ?? Target;
            return (
              <Card key={item.title} className="hover:border-primary/40">
                <CardHeader>
                  <div className="mb-2 flex size-10 items-center justify-center rounded-md border border-border bg-surface-2 text-primary">
                    <Icon className="size-5" />
                  </div>
                  <CardTitle>{item.title}</CardTitle>
                  <CardDescription>{item.body}</CardDescription>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
}
