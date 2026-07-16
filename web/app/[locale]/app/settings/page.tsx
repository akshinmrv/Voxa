import { setRequestLocale } from "next-intl/server";
import { SettingsView } from "@/components/app/settings-view";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <SettingsView />;
}
