import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { AppSidebar } from "@/components/app/app-sidebar";
import { AppTopbar } from "@/components/app/app-topbar";
import { QueryProvider } from "@/components/query-provider";

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

  return (
    <QueryProvider>
      <div className="flex flex-1">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopbar />
          <main className="flex-1 px-5 py-8 md:px-8">{children}</main>
        </div>
      </div>
    </QueryProvider>
  );
}
