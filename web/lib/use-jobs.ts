"use client";

import { useQuery } from "@tanstack/react-query";
import { listJobs } from "./api";
import type { JobSummary } from "./types";

const ACTIVE = new Set(["queued", "running"]);

/**
 * Every dub the server knows, shared by the sidebar, the status bar, the palette and the
 * Dubs page (one query, one cache). Asked every 2 s while one is going, else every 10 s.
 */
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: listJobs,
    refetchInterval: (query) =>
      query.state.data?.jobs.some((job) => ACTIVE.has(job.status)) ? 2000 : 10000,
  });
}

export function countJobs(jobs: JobSummary[] | undefined) {
  const count = { running: 0, queued: 0, review: 0 };
  for (const job of jobs ?? []) {
    if (job.status === "running") count.running++;
    else if (job.status === "queued") count.queued++;
    else if (job.status === "review") count.review++;
  }
  return count;
}
