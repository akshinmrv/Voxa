import { getTranslations, setRequestLocale } from "next-intl/server";
import { ListChecks } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { AppPageHeader } from "@/components/app/app-page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";

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
      <EmptyState
        icon={ListChecks}
        title={t("emptyTitle")}
        body={t("emptyBody")}
        action={
          <Button asChild>
            <Link href="/app">{t("emptyCta")}</Link>
          </Button>
        }
      />
    </>
  );
}
