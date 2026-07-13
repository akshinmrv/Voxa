import type { JobConfig, VoxaOptions } from "./types";

/**
 * Mock API for the operator app (D2). Shapes mirror the planned `voxa serve`
 * REST endpoints so D3 can swap these for real fetch calls (via React Query)
 * without touching the UI. No network happens here yet.
 */

const OPTIONS: VoxaOptions = {
  languages: [
    { code: "ru", name: "Russian" },
    { code: "tr", name: "Turkish" },
    { code: "az", name: "Azerbaijani" },
    { code: "en", name: "English" },
    { code: "de", name: "German" },
    { code: "fr", name: "French" },
    { code: "es", name: "Spanish" },
    { code: "it", name: "Italian" },
    { code: "pt", name: "Portuguese" },
    { code: "ar", name: "Arabic" },
  ],
  translators: [
    { id: "google", label: "Google", description: "Free, fast, no key required" },
    { id: "ollama", label: "Ollama", description: "Local LLM, fully offline", offline: true },
    { id: "openai", label: "OpenAI", description: "Context-aware, needs API key" },
    { id: "anthropic", label: "Anthropic", description: "Context-aware, needs API key" },
  ],
  ttsEngines: [
    { id: "edge", label: "Edge", description: "Cloud, many natural voices" },
    { id: "openai", label: "OpenAI", description: "Cloud or self-hosted endpoint" },
    { id: "piper", label: "Piper", description: "Fully offline neural TTS", offline: true },
    {
      id: "xtts",
      label: "XTTS",
      description: "Voice cloning from a sample",
      requiresVoiceSample: true,
    },
  ],
  whisperModels: [
    { id: "tiny", label: "tiny" },
    { id: "base", label: "base" },
    { id: "small", label: "small" },
    { id: "medium", label: "medium" },
    { id: "large", label: "large" },
  ],
};

/** GET /api/options — the model/engine registry. */
export async function getOptions(): Promise<VoxaOptions> {
  return OPTIONS;
}

/** Build the equivalent CLI command for a config (shown as a run preview). */
export function buildCommand(fileName: string, config: JobConfig): string {
  const parts = [
    "voxa",
    fileName || "video.mp4",
    `--target_lang ${config.targetLang}`,
    `--translator ${config.translator}`,
    `--tts ${config.tts}`,
    `--whisper_model ${config.whisperModel}`,
  ];
  if (config.tts === "xtts" && config.voiceSample) {
    parts.push(`--voice_sample ${config.voiceSample}`);
  }
  return parts.join(" ");
}
