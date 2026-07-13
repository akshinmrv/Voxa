import { useTranslations } from "next-intl";
import { ChevronDown } from "lucide-react";
import { SectionHeader } from "./section-header";

type Item = { q: string; a: string };

export function Faq() {
  const t = useTranslations("Faq");
  const items = t.raw("items") as Item[];

  return (
    <section id="faq" className="scroll-mt-20 border-t border-border bg-surface-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-24">
        <SectionHeader label={t("label")} title={t("title")} />
        <div className="mt-12 divide-y divide-border rounded-md border border-border">
          {items.map((item) => (
            <details key={item.q} className="group px-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-left font-medium marker:content-none">
                {item.q}
                <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180" />
              </summary>
              <p className="pb-4 text-sm text-pretty text-muted-foreground">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
