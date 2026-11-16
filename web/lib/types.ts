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
  /** TTS engines Voxa installs separately (Models page): false until installed. */
  available?: boolean;
};

/** Where an engine's install, started from the console, has got to. */
export type EngineInstall = {
  status: "idle" | "installing" | "done" | "failed";
  /** The install's latest output lines. */
  log: string[];
  error: string | null;
};

/** An engine Voxa installs into an environment of its own (GET /api/engines). */
export type InstallableEngine = {
  id: string;
  label: string;
  kind: string;
  description: string;
  /** The model weights' licence, as the model card gives it. */
  licence: string;
  /** What that licence allows commercially. */
  commercial: "yes" | "credit" | "no" | "unknown";
  languages: string[];
  cloning: boolean;
  /** Roughly what installing it downloads, packages and model together. */
  download_gb: number;
  homepage: string;
  notice: string;
  installed: boolean;
  installedAt?: string;
  path: string;
  install: EngineInstall;
};

export type WhisperModel = { id: string; label: string };

/** A composable speech-style preset (OpenAI TTS). Style only — timing stays locked. */
export type SpeechPreset = { id: string; label: string };

export type VoxaOptions = {
  languages: LanguageOption[];
  translators: EngineOption[];
  ttsEngines: EngineOption[];
  whisperModels: WhisperModel[];
  openaiTtsModels: WhisperModel[];
  openaiVoices: WhisperModel[];
  speechPresets: SpeechPreset[];
  /** Whether the optional pyannote extra is installed, so the form can offer diarization. */
  diarizeAvailable?: boolean;
  /** Whether the optional yt-dlp extra is installed, so the form can offer a URL source. */
  urlAvailable?: boolean;
  /** Whether Demucs is installed, so the form can offer keeping the music and effects. */
  separateAvailable?: boolean;
  /** The GPUs this machine has that the local models could use. */
  gpu?: { cuda: boolean; mps: boolean };
};

export type JobConfig = {
  targetLang: string;
  translator: string;
  tts: string;
  whisperModel: string;
  voiceSample?: string;
  openaiTtsModel?: string;
  openaiVoice?: string;
  diarize?: boolean;
  numSpeakers?: number;
  maxSpeakers?: number;
  /** Keep the original's music and effects, its speech taken out (Demucs). */
  separate?: boolean;
  /** Stop once the lines are translated, so they can be checked before any is voiced. */
  review?: boolean;
  /** Dub only the first this many seconds, to hear it before dubbing it all. */
  preview?: number | null;
  /** The Edge voice to speak with; null lets Voxa pick one. */
  edgeVoice?: string | null;
  /** A voice per speaker of a diarized job (an engine voice, or a library clip's id). */
  speakerVoices?: Record<string, string> | null;
  /** Subtitles, no speech. */
  subtitlesOnly?: boolean;
  /** The subtitles in the video: a track to turn on, or drawn onto the picture. */
  subtitlesInVideo?: "soft" | "hard" | null;
};

/** A voice to choose from (GET /api/voices). */
export type VoiceOption = {
  id: string;
  label: string;
  gender?: string | null;
  locale?: string;
  /** Edge: it can speak in styles (cheerful, sad…). */
  styles?: boolean;
  /** Piper: the model is on this machine (otherwise it downloads on first use). */
  installed?: boolean;
  /** A library clip's length. */
  seconds?: number | null;
};

export type VoiceList = {
  voices: VoiceOption[];
  /** The voices can be heard before a dub (Edge, Piper). */
  listen: boolean;
  /** The engine clones a voice: its choices are the clips of the voice library. */
  library?: boolean;
};

/** A clip kept to clone a voice from. */
export type LibraryVoice = { id: string; name: string; seconds: number; createdAt: number };

/** "review": translated, nothing voiced yet; waiting for the lines to be checked. */
export type JobStatus = "queued" | "running" | "review" | "done" | "failed";

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
  /** The job keeps its translated lines, which can be changed and voiced (again). */
  hasTranslation?: boolean;
  /** The original video is still in its folder (GET /api/jobs/{id}/source). */
  hasSource?: boolean;
  error: string | null;
  /** Epoch seconds: made, and its last run started and ended (null until it does). */
  createdAt?: number;
  startedAt?: number | null;
  finishedAt?: number | null;
  /** A queued job's place: 1 is next. */
  queuePosition?: number | null;
  /** Stopped from the console, rather than failed. */
  cancelled?: boolean;
};

/** One translated line of a job (GET /api/jobs/{id}/translation). */
export type TranslationLine = {
  /** Seconds into the video. */
  start: number;
  end: number;
  text: string;
  /** The line it was translated from. */
  source: string;
  speaker: string | null;
  /** About as many characters as fit its time; a longer line is spoken faster. */
  maxChars: number;
};

export type JobTranslation = { editable: boolean; lines: TranslationLine[] };

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
  translation: { prompt: string | null; fallback: string | null };
  speech: { instructions: string | null; presets: string[] };
  advanced: {
    speechRate: number | null;
    qualityGate: boolean;
    ttsWorkers: number | null;
    /** How many dubbing jobs may run at once (1 = one at a time). */
    maxConcurrentJobs: number | null;
    /** Save each dub automatically as soon as it finishes. */
    autoDownload: boolean;
    /** Ask PyPI once a day whether a newer Voxa is out. */
    checkUpdates: boolean;
    /** Where the local models run (voxa --device); null is "auto". */
    device: "auto" | "cpu" | "cuda" | "mps" | null;
  };
};

/** Partial update sent to PUT /api/settings — only changed fields. */
export type SettingsPatch = {
  defaultTranslator?: string;
  defaultTts?: string;
  providers?: Record<string, ProviderSettings>;
  translation?: { prompt?: string | null; fallback?: string | null };
  speech?: { instructions?: string | null; presets?: string[] };
  advanced?: {
    speechRate?: number | null;
    qualityGate?: boolean;
    ttsWorkers?: number | null;
    maxConcurrentJobs?: number | null;
    autoDownload?: boolean;
    checkUpdates?: boolean;
    device?: "auto" | "cpu" | "cuda" | "mps" | null;
  };
};

/** GET /api/update — this version, PyPI's newest, and how this install gets a newer one. */
export type UpdateStatus = {
  current: string;
  latest: string | null;
  newer: boolean;
  /** Turned off in Settings, or with VOXA_NO_UPDATE_CHECK. */
  disabled: boolean;
  /** How Voxa was installed; set only when a newer version is out. */
  kind: "setup" | "uv" | "pipx" | "pip" | "source" | "container" | null;
  /** The command that upgrades this install… */
  command: string | null;
  /** …or the installer to download instead (VoxaSetup.exe installs). */
  download: string | null;
  /** The new release's notes on GitHub. */
  notes: string | null;
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
