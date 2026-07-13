import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { ModelsView } from "@/components/app/models-view";

export default async function ModelsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.models");

  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />
      <ModelsView />
    </>
  );
}
