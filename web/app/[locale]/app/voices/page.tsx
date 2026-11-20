import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { Loading } from "@/components/app/query-states";
import { VoicesView } from "@/components/voices/voices-view";

export default async function VoicesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.voices");

  return (
    <>
      <AppPageHeader subtitle={t("subtitle")} />
      {/* The tab comes from ?tab=, read in the page: a static build has no server. */}
      <Suspense fallback={<Loading />}>
        <VoicesView />
      </Suspense>
    </>
  );
}
