import { getTranslations, setRequestLocale } from "next-intl/server";
import { Info } from "lucide-react";
import { AppPageHeader } from "@/components/app/app-page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("App.settings");

  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />

      <div className="max-w-2xl space-y-4">
        <div className="flex gap-3 rounded-md border border-primary/25 bg-primary/10 p-4">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">{t("note")}</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t("theme")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ThemeToggle />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("language")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LanguageSwitcher />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
