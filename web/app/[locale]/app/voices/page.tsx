import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { VoicesView } from "@/components/app/voices-view";

export default async function VoicesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.voices");

  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />
      <VoicesView />
    </>
  );
}
