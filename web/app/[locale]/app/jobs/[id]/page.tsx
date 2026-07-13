import { setRequestLocale } from "next-intl/server";
import { JobDetail } from "@/components/app/job-detail";

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);

  return <JobDetail jobId={id} />;
}
