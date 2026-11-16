"use client";

import { useTranslations } from "next-intl";
import { ArrowRight, FileVideo } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { useJobs } from "@/lib/use-jobs";
import { StatusBadge } from "@/components/app/status-badge";
import { MiniPath } from "./signal-path";

const SHOWN = 5;

/** The last few dubs under the composer, each a link to its page. */
export function RecentDubs() {
  const t = useTranslations("App.studio");
  const jobs = useJobs().data?.jobs ?? [];
  if (!jobs.length) return null;
  // The server lists them oldest first.
  const recent = jobs.slice(-SHOWN).reverse();
  return (
    <section aria-labelledby="recent-dubs" className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 id="recent-dubs" className="text-ui-label uppercase text-muted-foreground">
          {t("recent")}
        </h2>
        <Link
          href="/app/jobs"
          className="inline-flex items-center gap-1 text-ui-small text-muted-foreground transition-colors hover:text-foreground"
        >
          {t("allDubs")} <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
        {recent.map((job) => (
          <li key={job.id}>
            <Link
              href={{ pathname: "/app/jobs/view", query: { id: job.id } }}
              className="flex items-center gap-3 px-3 py-2.5 transition-colors duration-(--dur-1) hover:bg-surface-2"
            >
              <FileVideo className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="min-w-0 flex-1 truncate text-ui-body">{job.fileName}</span>
              <span className="font-mono text-ui-mono text-muted-foreground">
                {job.config.targetLang}
              </span>
              <span className="hidden w-16 text-ui-small text-muted-foreground sm:block">
                {job.config.subtitlesOnly ? "—" : job.config.tts}
              </span>
              <span className="hidden md:block">
                <MiniPath job={job} />
              </span>
              <StatusBadge status={job.status} cancelled={job.cancelled} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
