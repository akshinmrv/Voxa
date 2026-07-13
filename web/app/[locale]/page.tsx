import { setRequestLocale } from "next-intl/server";
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

  return (
    <>
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
