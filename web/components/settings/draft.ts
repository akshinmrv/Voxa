import type { SettingsPatch, VoxaSettings } from "@/lib/types";

/**
 * Every setting the page edits, flat, as its controls hold it (numbers as typed). The page
 * keeps changes here until "Save" sends them in one request (VOXA_DESIGN_PLAN.md §8.8);
 * keys are the exception, each saved on its own.
 */
export type Values = {
  defaultTranslator: string;
  defaultTts: string;
  prompt: string;
  fallback: string;
  presets: string[];
  instructions: string;
  qualityGate: boolean;
  autoDownload: boolean;
  checkUpdates: boolean;
  device: "auto" | "cpu" | "cuda" | "mps";
  speechRate: string;
  ttsWorkers: string;
  maxConcurrentJobs: string;
  /** Each LLM provider's default model, by provider. */
  models: Record<string, string>;
};

export type Draft = Partial<Values>;

const num = (value: number | null | undefined) => (value != null ? String(value) : "");

/** What is saved, in the controls' terms. */
export function savedValues(settings: VoxaSettings, providers: string[]): Values {
  return {
    defaultTranslator: settings.defaultTranslator,
    defaultTts: settings.defaultTts,
    prompt: settings.translation?.prompt ?? "",
    fallback: settings.translation?.fallback ?? "",
    presets: settings.speech?.presets ?? [],
    instructions: settings.speech?.instructions ?? "",
    qualityGate: settings.advanced?.qualityGate ?? false,
    autoDownload: settings.advanced?.autoDownload ?? false,
    checkUpdates: settings.advanced?.checkUpdates ?? true,
    device: settings.advanced?.device ?? "auto",
    speechRate: num(settings.advanced?.speechRate),
    ttsWorkers: num(settings.advanced?.ttsWorkers),
    maxConcurrentJobs: num(settings.advanced?.maxConcurrentJobs),
    models: Object.fromEntries(
      providers.map((pid) => [pid, settings.providers?.[pid]?.model ?? ""]),
    ),
  };
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The settings changed and not saved: one per field, one per provider's model. */
export function changes(draft: Draft, saved: Values): string[] {
  const out: string[] = [];
  for (const [key, value] of Object.entries(draft) as [keyof Values, unknown][]) {
    if (key === "models") {
      for (const [pid, model] of Object.entries(value as Record<string, string>)) {
        if (model.trim() !== (saved.models[pid] ?? "")) out.push(`models.${pid}`);
      }
    } else if (key === "prompt" || key === "instructions") {
      if ((value as string).trim() !== saved[key]) out.push(key);
    } else if (!same(value, saved[key])) {
      out.push(key);
    }
  }
  return out;
}

const toNumber = (value: string) => (value.trim() ? Number(value) : null);

/** The request that saves the changes, and nothing else. */
export function toPatch(draft: Draft, saved: Values): SettingsPatch {
  const changed = new Set(changes(draft, saved));
  const patch: SettingsPatch = {};
  const v = { ...saved, ...draft };
  if (changed.has("defaultTranslator")) patch.defaultTranslator = v.defaultTranslator;
  if (changed.has("defaultTts")) patch.defaultTts = v.defaultTts;
  if (changed.has("prompt") || changed.has("fallback")) {
    patch.translation = {};
    if (changed.has("prompt")) patch.translation.prompt = v.prompt.trim() || null;
    if (changed.has("fallback")) patch.translation.fallback = v.fallback || null;
  }
  if (changed.has("presets") || changed.has("instructions")) {
    patch.speech = {};
    if (changed.has("presets")) patch.speech.presets = v.presets;
    if (changed.has("instructions")) patch.speech.instructions = v.instructions.trim() || null;
  }
  const advanced: NonNullable<SettingsPatch["advanced"]> = {};
  if (changed.has("qualityGate")) advanced.qualityGate = v.qualityGate;
  if (changed.has("autoDownload")) advanced.autoDownload = v.autoDownload;
  if (changed.has("checkUpdates")) advanced.checkUpdates = v.checkUpdates;
  if (changed.has("device")) advanced.device = v.device;
  if (changed.has("speechRate")) advanced.speechRate = toNumber(v.speechRate);
  if (changed.has("ttsWorkers")) advanced.ttsWorkers = toNumber(v.ttsWorkers);
  if (changed.has("maxConcurrentJobs")) advanced.maxConcurrentJobs = toNumber(v.maxConcurrentJobs);
  if (Object.keys(advanced).length) patch.advanced = advanced;
  const models = [...changed].filter((c) => c.startsWith("models."));
  if (models.length) {
    patch.providers = Object.fromEntries(
      models.map((c) => {
        const pid = c.slice("models.".length);
        return [pid, { model: (draft.models?.[pid] ?? "").trim() || null }];
      }),
    );
  }
  return patch;
}
