import { getTranslations, setRequestLocale } from "next-intl/server";
import { landingJsonLd } from "@/lib/structured-data";
import { JsonLd } from "@/components/seo/json-ld";
import { LandingHeader } from "@/components/landing/landing-header";
import { Hero } from "@/components/landing/hero";
import { Why } from "@/components/landing/why";
import { Features } from "@/components/landing/features";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Models } from "@/components/landing/models";
import { Installation } from "@/components/landing/installation";
import { QuickStart } from "@/components/landing/quick-start";
import { Faq } from "@/components/landing/faq";
import { LandingFooter } from "@/components/landing/landing-footer";

export default async function LandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const meta = await getTranslations("Meta");
  const faq = await getTranslations("Faq");
  const jsonLd = landingJsonLd({
    locale,
    description: meta("description"),
    faq: faq.raw("items") as { q: string; a: string }[],
  });

  return (
    <>
      <JsonLd data={jsonLd} />
      <LandingHeader />
      <main className="flex-1">
        <Hero />
        <Why />
        <Features />
        <HowItWorks />
        <Models />
        <Installation />
        <QuickStart />
        <Faq />
      </main>
      <LandingFooter />
    </>
  );
}
