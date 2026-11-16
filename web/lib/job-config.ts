import type { JobConfig, VoxaOptions, VoxaSettings } from "./types";

/** What the user changed in the Studio; anything left out comes from Settings or the options. */
export type ConfigChoice = Partial<JobConfig> & {
  /** Every language to dub into: one job each. */
  targetLangs?: string[];
  /** An Edge voice per language (null: Voxa picks). */
  edgeVoices?: Record<string, string | null>;
};

/** The translators that need a key of their own (an LLM provider's). */
export const KEYED_TRANSLATORS = new Set(["openai", "anthropic", "openrouter"]);

/**
 * The job a choice amounts to: the user's choice, else the saved default, else the first
 * option. An engine Voxa installs separately is taken only once installed, even as the saved
 * default (which may name one removed since).
 */
export function effectiveConfig(
  choice: ConfigChoice,
  options: VoxaOptions,
  settings: VoxaSettings | undefined,
): JobConfig & {
  targetLangs: string[];
  edgeVoices: Record<string, string | null>;
} {
  const usableTts = (id?: string) =>
    options.ttsEngines.some((e) => e.id === id && e.available !== false) ? id : undefined;
  const known = new Set(options.languages.map((l) => l.code));
  const langs = (choice.targetLangs ?? []).filter((code) => known.has(code));
  const targetLangs = langs.length ? langs : [options.languages[0]?.code ?? "en"];
  return {
    targetLang: targetLangs[0],
    targetLangs,
    translator:
      choice.translator ?? settings?.defaultTranslator ?? options.translators[0]?.id ?? "google",
    tts:
      usableTts(choice.tts) ??
      usableTts(settings?.defaultTts) ??
      options.ttsEngines.find((e) => e.available !== false)?.id ??
      "edge",
    whisperModel: choice.whisperModel ?? "base",
    edgeVoice: null,
    edgeVoices: choice.edgeVoices ?? {},
    voiceSample: choice.voiceSample,
    openaiTtsModel: choice.openaiTtsModel ?? options.openaiTtsModels[0]?.id ?? "gpt-4o-mini-tts",
    openaiVoice: choice.openaiVoice ?? options.openaiVoices[0]?.id ?? "alloy",
    diarize: !!options.diarizeAvailable && (choice.diarize ?? false),
    numSpeakers: choice.numSpeakers,
    separate: !!options.separateAvailable && (choice.separate ?? false),
    review: choice.review ?? false,
    subtitlesOnly: choice.subtitlesOnly ?? false,
    subtitlesInVideo: choice.subtitlesInVideo ?? null,
  };
}

/** The config one language's job is sent with. */
export function configFor(
  config: ReturnType<typeof effectiveConfig>,
  lang: string,
  preview: number | null,
): JobConfig {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { targetLangs, edgeVoices, ...rest } = config;
  return {
    ...rest,
    targetLang: lang,
    edgeVoice: config.tts === "edge" ? (edgeVoices[lang] ?? null) : null,
    preview,
  };
}
