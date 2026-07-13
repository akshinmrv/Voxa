import { useTranslations } from "next-intl";
import { SectionHeader } from "./section-header";

type Step = { title: string; body: string };

export function HowItWorks() {
  const t = useTranslations("HowItWorks");
  const steps = t.raw("steps") as Step[];

  return (
    <section id="how-it-works" className="scroll-mt-20 border-y border-border bg-surface-1">
      <div className="mx-auto w-full max-w-6xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />
        <ol className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <li
              key={step.title}
              className="relative rounded-md border border-border bg-background p-5"
            >
              <span className="type-code inline-flex size-8 items-center justify-center rounded-sm border border-primary/30 bg-primary/10 text-sm font-medium text-primary tabular">
                {String(i + 1).padStart(2, "0")}
              </span>
              <h3 className="type-h3 mt-4">{step.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
