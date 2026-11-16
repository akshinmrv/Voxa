"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ChevronRight, Menu, Search } from "lucide-react";
import { Link, usePathname } from "@/i18n/navigation";
import { getJob } from "@/lib/api";
import { keyLabel } from "@/lib/shortcuts";
import { Kbd } from "@/components/ui/kbd";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Waveform } from "@/components/waveform";
import { sectionOf } from "@/components/app/nav-items";
import { NavList } from "./sidebar";
import { useShell } from "./shell-context";

/** A dub's page: "Dubs › its file", the file named from the same query the page uses. */
function JobCrumb({ section }: { section: string }) {
  const id = useSearchParams().get("id") ?? "";
  const job = useQuery({ queryKey: ["job", id], queryFn: () => getJob(id), enabled: !!id });
  const name = job.data?.fileName ?? "";
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <Link
        href="/app/jobs"
        className="shrink-0 text-ui-body text-muted-foreground transition-colors hover:text-foreground"
      >
        {section}
      </Link>
      <ChevronRight className="size-4 shrink-0 text-fg-subtle" aria-hidden />
      <h1 className="min-w-0 truncate text-ui-section" title={name}>
        {name || "…"}
      </h1>
    </div>
  );
}

/**
 * The bar over each page: where you are, and the way to everything else (Ctrl+K). Language
 * and theme moved to Settings and the palette; a page's own actions come here later (S3).
 */
export function Header() {
  const t = useTranslations("App");
  const common = useTranslations("Common");
  const pathname = usePathname();
  const { openPalette } = useShell();
  const [menu, setMenu] = useState(false);
  const section = sectionOf(pathname);
  const title = section ? t(`nav.${section.key}`) : "Voxa";
  const onJob = pathname.startsWith("/app/jobs/view");

  return (
    <header className="flex h-13 shrink-0 items-center gap-3 border-b border-border px-4 md:px-6">
      <Button
        variant="ghost"
        size="icon-sm"
        className="md:hidden"
        aria-label={t("shell.menu")}
        onClick={() => setMenu(true)}
      >
        <Menu />
      </Button>
      <Dialog open={menu} onOpenChange={setMenu}>
        <DialogContent
          closeLabel={common("close")}
          className="left-0 top-0 h-dvh w-72 max-w-none translate-x-0 translate-y-0 content-start rounded-none border-y-0 border-l-0 p-3"
        >
          <DialogTitle className="flex items-center gap-2.5 px-3 pb-2 pt-1">
            <Waveform bars={4} animated={false} className="h-[18px]" />
            <span className="text-ui-section">Voxa</span>
          </DialogTitle>
          <NavList onNavigate={() => setMenu(false)} />
        </DialogContent>
      </Dialog>

      <div className="min-w-0 flex-1">
        {onJob ? (
          <Suspense fallback={<h1 className="text-ui-section">{title}</h1>}>
            <JobCrumb section={title} />
          </Suspense>
        ) : (
          <h1 className="truncate text-ui-section">{title}</h1>
        )}
      </div>

      <button
        type="button"
        onClick={openPalette}
        aria-label={t("shell.palette.title")}
        className="flex h-8 shrink-0 items-center gap-2 rounded-sm border border-border bg-surface-1 px-2.5 text-ui-small text-muted-foreground transition-colors duration-(--dur-1) hover:border-border-strong hover:text-foreground sm:w-64"
      >
        <Search className="size-4 shrink-0" aria-hidden />
        <span className="hidden flex-1 truncate text-left sm:block">{t("shell.search")}</span>
        <Kbd className="hidden sm:inline-flex">{keyLabel(["Mod", "K"])}</Kbd>
      </button>
    </header>
  );
}
