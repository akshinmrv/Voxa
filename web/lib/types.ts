// Shared domain types for the operator app. The mock API in lib/api.ts returns
// these shapes; the real `voxa serve` backend (D3) will return the same ones.

export type LanguageOption = { code: string; name: string };

export type EngineOption = {
  id: string;
  label: string;
  description: string;
  /** TTS engines only: needs a reference clip (e.g. XTTS voice cloning). */
  requiresVoiceSample?: boolean;
  /** Runs without any network calls. */
  offline?: boolean;
  /** LLM translators only: the engine's built-in default model (UI placeholder). */
  defaultModel?: string;
};

export type WhisperModel = { id: string; label: string };

export type VoxaOptions = {
  languages: LanguageOption[];
  translators: EngineOption[];
  ttsEngines: EngineOption[];
  whisperModels: WhisperModel[];
  openaiTtsModels: WhisperModel[];
  openaiVoices: WhisperModel[];
};

export type JobConfig = {
  targetLang: string;
  translator: string;
  tts: string;
  whisperModel: string;
  voiceSample?: string;
  openaiTtsModel?: string;
  openaiVoice?: string;
};

export type JobStatus = "queued" | "running" | "done" | "failed";

/** Mirrors voxa_server.Job.summary(). */
export type JobSummary = {
  id: string;
  fileName: string;
  config: JobConfig;
  status: JobStatus;
  step: number;
  totalSteps: number;
  hasVideo: boolean;
  hasSrt: boolean;
  error: string | null;
};

/** A single Server-Sent Event from GET /api/jobs/{id}/events. */
export type JobEvent =
  | { type: "status"; status: JobStatus; error?: string }
  | { type: "step"; step: number; status: "running" | "done" }
  | { type: "log"; line: string };

// ── Settings (P0) — mirrors voxa_server's settings.json shape ───────────────

/** Persisted operator settings. Nested groups are placeholders that later phases
 *  (translation prompt, speech style, advanced timing) populate; null = engine default. */
/** Per-LLM-provider default translation model (null = the engine's built-in default). */
export type ProviderSettings = { model: string | null };

export type VoxaSettings = {
  version: number;
  defaultTranslator: string;
  defaultTts: string;
  providers: Record<string, ProviderSettings>;
  translation: { prompt: string | null };
  speech: { instructions: string | null; presets: string[] };
  advanced: { speechRate: number | null };
};

/** Partial update sent to PUT /api/settings — only changed fields. */
export type SettingsPatch = {
  defaultTranslator?: string;
  defaultTts?: string;
  providers?: Record<string, ProviderSettings>;
  translation?: { prompt?: string | null };
  speech?: { instructions?: string | null; presets?: string[] };
  advanced?: { speechRate?: number | null };
};

/** Masked API-key status for one provider (the raw key never reaches the browser). */
export type ProviderKeyStatus = {
  provider: string;
  envKey: string;
  hasKey: boolean;
  masked: string | null;
};

/** Result of POST /api/providers/{id}/test — a cheap key/reachability check. */
export type ProviderTestResult = { ok: boolean; error?: string; latencyMs?: number };
