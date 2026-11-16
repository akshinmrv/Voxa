import { setRequestLocale } from "next-intl/server";
import { Composer } from "@/components/studio/composer";

export default async function StudioPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Composer />;
}
