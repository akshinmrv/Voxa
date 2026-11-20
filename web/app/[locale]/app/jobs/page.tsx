import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppPageHeader } from "@/components/app/app-page-header";
import { LibraryView } from "@/components/library/library-view";

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
      <AppPageHeader subtitle={t("subtitle")} />
      <LibraryView />
    </>
  );
}
