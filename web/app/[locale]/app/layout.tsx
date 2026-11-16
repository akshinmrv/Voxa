import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { IS_PUBLIC } from "@/lib/site";
import { QueryProvider } from "@/components/query-provider";
import { LocalOnlyNotice } from "@/components/app/local-only-notice";
import { AppFrame } from "@/components/shell/app-frame";
import { SIDEBAR_SCRIPT } from "@/components/shell/sidebar-state";

// The operator console runs locally; keep it out of search indexes on any public deploy.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  // Public deploy: the operator app is local-only — show the "run locally" notice.
  if (IS_PUBLIC) {
    return <LocalOnlyNotice />;
  }

  return (
    <QueryProvider>
      {/* Before the sidebar is drawn: open it as it was left (sidebar-state.ts). */}
      <script dangerouslySetInnerHTML={{ __html: SIDEBAR_SCRIPT }} />
      <AppFrame>{children}</AppFrame>
    </QueryProvider>
  );
}
