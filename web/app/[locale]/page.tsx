import { getTranslations, setRequestLocale } from "next-intl/server";
import { landingJsonLd } from "@/lib/structured-data";
import { DEMO_VIDEO, DEMO_POSTER } from "@/lib/site";
import { JsonLd } from "@/components/seo/json-ld";
import { LandingHeader } from "@/components/landing/landing-header";
import { Hero } from "@/components/landing/hero";
import { Demo } from "@/components/landing/demo";
import { Why } from "@/components/landing/why";
import { Features } from "@/components/landing/features";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Models } from "@/components/landing/models";
import { Installation } from "@/components/landing/installation";
import { QuickStart } from "@/components/landing/quick-start";
import { Faq } from "@/components/landing/faq";
import { Author } from "@/components/landing/author";
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
  const demoT = await getTranslations("Demo");
  const jsonLd = landingJsonLd({
    locale,
    description: meta("description"),
    faq: faq.raw("items") as { q: string; a: string }[],
    demo: DEMO_VIDEO
      ? {
          url: DEMO_VIDEO,
          poster: DEMO_POSTER,
          name: `${demoT("title")} — Voxa`,
          description: demoT("subtitle"),
        }
      : null,
  });

  return (
    <>
      <JsonLd data={jsonLd} />
      <LandingHeader />
      <main id="main-content" className="flex-1">
        <Hero />
        <Demo />
        <Why />
        <Features />
        <HowItWorks />
        <Models />
        <Installation />
        <QuickStart />
        <Faq />
        <Author />
      </main>
      <LandingFooter />
    </>
  );
}
