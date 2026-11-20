import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { SystemView } from "@/components/system/system-view";

export default async function SystemPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.system");

  return (
    <>
      <AppPageHeader subtitle={t("subtitle")} />
      <SystemView />
    </>
  );
}
