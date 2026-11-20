"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { toast } from "@/lib/toast";
import type { JobStatus } from "@/lib/types";
import { useJobs } from "@/lib/use-jobs";
import { useUpdateStatus } from "@/lib/use-update";

const GOING: JobStatus[] = ["queued", "running"];
const TOLD_UPDATE = "voxa.update.told";

/**
 * Notes for what happens while you look elsewhere in the console (VOXA_DESIGN_PLAN.md §7.5):
 * a dub done, waiting for its lines to be checked, or failed, each with the way to it; and a
 * newer Voxa, once per version. A dub seen finishing on its own page isn't announced there.
 * Behind other windows, Voxa Studio's taskbar button flashes instead (voxa_studio.watch_jobs).
 */
export function Notices() {
  const t = useTranslations("App.notices");
  const jobs = useJobs().data?.jobs;
  const update = useUpdateStatus().data;
  const seen = useRef<Map<string, JobStatus> | null>(null);

  useEffect(() => {
    if (!jobs) return;
    const before = seen.current;
    seen.current = new Map(jobs.map((job) => [job.id, job.status]));
    if (!before) return; // what was so when the console opened isn't news
    const params = new URLSearchParams(window.location.search);
    const onItsPage = (id: string) =>
      window.location.pathname.includes("/app/jobs/view") && params.get("id") === id;
    for (const job of jobs) {
      const was = before.get(job.id);
      if (!was || !GOING.includes(was) || GOING.includes(job.status) || onItsPage(job.id)) continue;
      const href = `/app/jobs/view?id=${job.id}`;
      const name = job.fileName;
      if (job.status === "done") {
        toast(
          job.config.subtitlesOnly ? t("subtitled", { name }) : t("done", { name }),
          "success",
          {
            action: { label: t("open"), href },
          },
        );
      } else if (job.status === "review") {
        toast(t("review", { name }), "warning", { action: { label: t("check"), href } });
      } else if (job.status === "failed" && !job.cancelled) {
        toast(t("failed", { name, reason: job.error ?? "" }), "error", {
          action: { label: t("open"), href },
          sticky: true,
        });
      }
    }
  }, [jobs, t]);

  useEffect(() => {
    if (!update?.newer || !update.latest) return;
    try {
      if (window.localStorage.getItem(TOLD_UPDATE) === update.latest) return;
      window.localStorage.setItem(TOLD_UPDATE, update.latest);
    } catch {
      /* storage blocked: said once per visit */
    }
    toast(t("update", { latest: update.latest }), "info", {
      action: { label: t("howToUpdate"), href: "/app/settings?section=about" },
      sticky: true,
    });
  }, [update, t]);

  return null;
}
