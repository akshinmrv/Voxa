import { API_BASE } from "./config";
import type {
  InstallableEngine,
  JobConfig,
  JobSummary,
  JobTranslation,
  ProviderKeyStatus,
  ProviderTestResult,
  SettingsPatch,
  UpdateStatus,
  VoxaOptions,
  VoxaSettings,
} from "./types";

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
  source: { fileId?: string; sourceUrl?: string },
  config: JobConfig,
): Promise<{ jobId: string }> {
  return asJson(
    await fetch(`${API_BASE}/api/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...source, config }),
    }),
  );
}

export async function getJob(id: string): Promise<JobSummary> {
  return asJson(await fetch(`${API_BASE}/api/jobs/${id}`));
}

export async function listJobs(): Promise<{ jobs: JobSummary[] }> {
  return asJson(await fetch(`${API_BASE}/api/jobs`));
}

// ── Settings & API keys (P0) ────────────────────────────────────────────────

export async function getTranslation(id: string): Promise<JobTranslation> {
  return asJson(await fetch(`${API_BASE}/api/jobs/${id}/translation`));
}

/** One text per line, in order: only the words change, never the timing. */
export async function putTranslation(id: string, texts: string[]): Promise<JobTranslation> {
  return asJson(
    await fetch(`${API_BASE}/api/jobs/${id}/translation`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texts }),
    }),
  );
}

/** Voice the job's lines as they are: after a review, or again after changing some. */
export async function voiceJob(id: string): Promise<JobSummary> {
  return asJson(await fetch(`${API_BASE}/api/jobs/${id}/voice`, { method: "POST" }));
}

export async function getSettings(): Promise<VoxaSettings> {
  return asJson(await fetch(`${API_BASE}/api/settings`));
}

export async function updateSettings(patch: SettingsPatch): Promise<VoxaSettings> {
  return asJson(
    await fetch(`${API_BASE}/api/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  );
}

export async function resetSettings(): Promise<VoxaSettings> {
  return asJson(await fetch(`${API_BASE}/api/settings/reset`, { method: "POST" }));
}

export async function getKeys(): Promise<{ keys: ProviderKeyStatus[] }> {
  return asJson(await fetch(`${API_BASE}/api/keys`));
}

export async function putKey(
  provider: string,
  value: string,
): Promise<{ keys: ProviderKeyStatus[] }> {
  return asJson(
    await fetch(`${API_BASE}/api/keys/${provider}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    }),
  );
}

export async function deleteKey(provider: string): Promise<{ keys: ProviderKeyStatus[] }> {
  return asJson(await fetch(`${API_BASE}/api/keys/${provider}`, { method: "DELETE" }));
}

export async function testProvider(provider: string): Promise<ProviderTestResult> {
  return asJson(
    await fetch(`${API_BASE}/api/providers/${provider}/test`, { method: "POST" }),
  );
}

// ── Engines installed into environments of their own ──────────────────────────
export async function getUpdate(): Promise<UpdateStatus> {
  return asJson(await fetch(`${API_BASE}/api/update`));
}

export async function getEngines(): Promise<{ engines: InstallableEngine[]; dir: string }> {
  return asJson(await fetch(`${API_BASE}/api/engines`));
}

export async function installEngine(id: string): Promise<InstallableEngine> {
  return asJson(await fetch(`${API_BASE}/api/engines/${id}/install`, { method: "POST" }));
}

export async function removeEngine(id: string): Promise<InstallableEngine> {
  return asJson(await fetch(`${API_BASE}/api/engines/${id}`, { method: "DELETE" }));
}

export const jobEventsUrl = (id: string) => `${API_BASE}/api/jobs/${id}/events`;
export const resultVideoUrl = (id: string) =>
  `${API_BASE}/api/jobs/${id}/result/video`;
export const resultSrtUrl = (id: string) =>
  `${API_BASE}/api/jobs/${id}/result/srt`;
