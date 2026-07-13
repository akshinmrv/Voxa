import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { NewJobFlow } from "@/components/app/new-job-flow";

export default async function NewJobPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.newJob");

  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />
      <NewJobFlow />
    </>
  );
}
