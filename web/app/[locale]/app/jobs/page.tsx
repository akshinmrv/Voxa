import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { JobsView } from "@/components/app/jobs-view";

export default async function JobsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.jobs");

  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />
      <JobsView />
    </>
  );
}
