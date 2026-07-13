import { API_BASE } from "./config";
import type { JobConfig, JobSummary, VoxaOptions } from "./types";

/**
 * Client for the `voxa serve` backend. Every call hits the local API at
 * API_BASE; React Query wraps these with caching, loading, and error state.
 */

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function getOptions(): Promise<VoxaOptions> {
  return asJson(await fetch(`${API_BASE}/api/options`));
}

export async function uploadVideo(
  file: File,
): Promise<{ fileId: string; fileName: string; size: number }> {
  const form = new FormData();
  form.append("file", file);
  return asJson(await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form }));
}

export async function createJob(
  fileId: string,
  config: JobConfig,
): Promise<{ jobId: string }> {
  return asJson(
    await fetch(`${API_BASE}/api/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileId, config }),
    }),
  );
}

export async function getJob(id: string): Promise<JobSummary> {
  return asJson(await fetch(`${API_BASE}/api/jobs/${id}`));
}

export async function listJobs(): Promise<{ jobs: JobSummary[] }> {
  return asJson(await fetch(`${API_BASE}/api/jobs`));
}

export const jobEventsUrl = (id: string) => `${API_BASE}/api/jobs/${id}/events`;
export const resultVideoUrl = (id: string) =>
  `${API_BASE}/api/jobs/${id}/result/video`;
export const resultSrtUrl = (id: string) =>
  `${API_BASE}/api/jobs/${id}/result/srt`;
