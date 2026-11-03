import { Suspense } from "react";
import { setRequestLocale } from "next-intl/server";
import { JobDetailFromQuery } from "@/components/app/job-detail";
import { Loading } from "@/components/app/query-states";

// /app/jobs/view?id=<job id>. The id is read in the browser (see JobDetailFromQuery), so the
// page prerenders without knowing any job, as the bundled static console requires.
export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <Suspense fallback={<Loading />}>
      <JobDetailFromQuery />
    </Suspense>
  );
}
