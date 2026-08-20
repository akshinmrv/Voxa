"use client";

import { useEffect, useRef } from "react";
import { resultVideoUrl } from "./api";
import type { JobStatus } from "./types";

/** The shape this hook needs from a job — the list and the detail page both provide it. */
export type Downloadable = { id: string; status: JobStatus; hasVideo: boolean };

/**
 * Save a job's video as soon as its dub finishes, when the operator has turned that on in
 * Settings.
 *
 * Only a job that is *seen finishing* triggers a download: statuses are recorded on every
 * update, and a download fires when a job that was previously queued or running turns up
 * done. A job that was already finished when the page opened is recorded and left alone —
 * otherwise opening the jobs list would download the entire history at once.
 *
 * Downloads only happen while the console is open, and a browser may ask for permission
 * before saving several files from one page.
 */
export function useAutoDownload(jobs: Downloadable[] | undefined, enabled: boolean) {
  const lastStatus = useRef(new Map<string, JobStatus>());

  useEffect(() => {
    if (!jobs) return;
    for (const job of jobs) {
      const before = lastStatus.current.get(job.id);
      lastStatus.current.set(job.id, job.status);
      if (!enabled) continue;                       // still recorded, so enabling it later
      if (before === undefined || before === "done") continue;   // not a fresh completion
      if (job.status !== "done" || !job.hasVideo) continue;

      // The result endpoint sends Content-Disposition, so the browser saves the file with
      // the name the server chose rather than navigating to it.
      const link = document.createElement("a");
      link.href = resultVideoUrl(job.id);
      link.download = "";
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
  }, [jobs, enabled]);
}
