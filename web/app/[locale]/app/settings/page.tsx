import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { Loading } from "@/components/app/query-states";
import { SettingsView } from "@/components/settings/settings-view";

export default async function SettingsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.settings");
  return (
    <>
      <AppPageHeader subtitle={t("subtitle")} />
      {/* The section comes from ?section=, read in the page: a static build has no server. */}
      <Suspense fallback={<Loading />}>
        <SettingsView />
      </Suspense>
    </>
  );
}
