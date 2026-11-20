"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  Check,
  ChevronDown,
  Headphones,
  KeyRound,
  Play,
  WifiOff,
  Copy as Clone,
} from "lucide-react";
import { createJob, getKeys, getOptions, getSettings, uploadVideo } from "@/lib/api";
import {
  configFor,
  effectiveConfig,
  KEYED_TRANSLATORS,
  STUDIO_CHOICE_KEY,
  type ConfigChoice,
} from "@/lib/job-config";
import { keyLabel } from "@/lib/shortcuts";
import { useLanguageNames } from "@/lib/use-language-names";
import { Link, useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { SegmentedControl } from "@/components/ui/segmented";
import { ChoiceCard, ChoiceCards } from "@/components/ui/choice-card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { BackendError, Loading } from "@/components/app/query-states";
import { cn } from "@/lib/utils";
import {
  SourcePicker,
  fileKey,
  formatDuration,
  useDurations,
  type SourceMode,
} from "./source-picker";
import { VoiceChoice } from "./voice-choice";
import { PlannedPath } from "./signal-path";
import { RecentDubs } from "./recent-dubs";

/** How much of the video a preview dubs, from its start. */
const PREVIEW_SECONDS = 20;
/** The choices outlive a visit to another page (not the files: a browser can't keep those). */
const KEPT = STUDIO_CHOICE_KEY;

function readKept(): ConfigChoice {
  try {
    return JSON.parse(window.sessionStorage.getItem(KEPT) ?? "{}") as ConfigChoice;
  } catch {
    return {};
  }
}

function Section({
  n,
  id,
  title,
  children,
}: {
  n: number;
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden
          className="flex size-5 items-center justify-center rounded-full border border-border-strong font-mono text-[11px] text-muted-foreground"
        >
          {n}
        </span>
        <h2 id={id} className="text-ui-section">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

/** A setting on one line: what it is (and a hint) on the left, its control on the right. */
function Row({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-6 py-3">
      <div className="min-w-0">
        <label htmlFor={id} className="text-ui-body font-medium">
          {label}
        </label>
        {hint && <p className="mt-0.5 text-ui-small text-muted-foreground">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

/**
 * The Studio: a dub put together top to bottom — the videos, the languages, how to translate,
 * how to speak, the rest — with what it will do summed up beside it (VOXA_DESIGN_PLAN.md §8.1).
 */
export function Composer() {
  const tn = useTranslations("App.newJob");
  const ts = useTranslations("App.studio");
  const router = useRouter();
  const optionsQuery = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });
  // Which keys are set: a remote console isn't told (403), and then nothing is held back.
  const keysQuery = useQuery({
    queryKey: ["keys"],
    queryFn: getKeys,
    retry: false,
  });

  const [choice, setChoice] = useState<ConfigChoice>(readKept);
  const [mode, setMode] = useState<SourceMode>("file");
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState("");
  const [started, setStarted] = useState({ done: 0, total: 0 });
  const [more, setMore] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const durations = useDurations(files);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(KEPT, JSON.stringify(choice));
    } catch {
      /* not kept: the choices start over next visit */
    }
  }, [choice]);

  const names = useLanguageNames();

  const options = optionsQuery.data;
  const config = options ? effectiveConfig(choice, options, settingsQuery.data) : null;
  const urlMode = mode === "url" && !!options?.urlAvailable;
  const sources = urlMode ? (url.trim() ? 1 : 0) : files.length;
  const jobs = sources * (config?.targetLangs.length ?? 1);

  const submit = useMutation({
    mutationFn: async (preview: number | null) => {
      if (!config) return [];
      const langs = config.targetLangs;
      const total = (urlMode ? 1 : files.length) * langs.length;
      const ids: string[] = [];
      const made = (id: string) => {
        ids.push(id);
        setStarted({ done: ids.length, total });
      };
      setStarted({ done: 0, total });
      if (urlMode) {
        for (const lang of langs) {
          made(
            (await createJob({ sourceUrl: url.trim() }, configFor(config, lang, preview))).jobId,
          );
        }
      } else {
        // One upload per video, then a job per language from it: they share its work dir, so
        // the second language reuses the first one's transcription.
        for (const file of files) {
          const { fileId } = await uploadVideo(file);
          for (const lang of langs) {
            made((await createJob({ fileId }, configFor(config, lang, preview))).jobId);
          }
        }
      }
      return ids;
    },
    onSuccess: (ids) =>
      router.push(
        ids.length === 1 ? { pathname: "/app/jobs/view", query: { id: ids[0] } } : "/app/jobs",
      ),
  });

  const translator = options?.translators.find((e) => e.id === config?.translator);
  const engine = options?.ttsEngines.find((e) => e.id === config?.tts);
  const hasKey = (provider: string) =>
    keysQuery.data?.keys.find((k) => k.provider === provider)?.hasKey;
  const keyMissing =
    !!config && KEYED_TRANSLATORS.has(config.translator) && hasKey(config.translator) === false;
  const blocked = sources === 0 ? (urlMode ? tn("runHintUrl") : tn("runHint")) : null;
  const canRun = !!config && !blocked && !keyMissing && !submit.isPending;

  // Ctrl+Enter starts the dub, Ctrl+O chooses videos (lib/shortcuts.ts lists them).
  const keys = useRef({ run: () => {}, open: () => {} });
  useEffect(() => {
    keys.current = {
      run: () => canRun && submit.mutate(null),
      open: () => {
        setMode("file");
        inputRef.current?.click();
      },
    };
  });
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
      if (event.key === "Enter") {
        event.preventDefault();
        keys.current.run();
      } else if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        keys.current.open();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (optionsQuery.isPending) return <Loading />;
  if (optionsQuery.isError || !options || !config)
    return <BackendError onRetry={() => optionsQuery.refetch()} />;

  const set = (patch: ConfigChoice) => setChoice((c) => ({ ...c, ...patch }));
  const langName = (code: string) =>
    names(code, options.languages.find((l) => l.code === code)?.name ?? code);
  const toggleLang = (code: string) => {
    const now = config.targetLangs;
    // The last language stays: a dub needs one.
    if (now.includes(code) && now.length === 1) return;
    set({
      targetLangs: now.includes(code) ? now.filter((c) => c !== code) : [...now, code],
    });
  };
  const description = (kind: "translators" | "engines", id: string, fallback: string) =>
    ts.has(`${kind}.${id}`) ? ts(`${kind}.${id}` as "translators.google") : fallback;
  const totalSeconds = files.reduce((sum, f) => sum + (durations[fileKey(f)] ?? 0), 0);
  const moreSummary = [
    ts("moreWhisper", { model: config.whisperModel }),
    config.diarize && !config.subtitlesOnly ? ts("moreSpeakers") : null,
    config.separate && !config.subtitlesOnly ? ts("moreBackground") : null,
    config.review ? ts("moreReview") : null,
    config.subtitlesInVideo ? ts("moreSubtitles") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  // In the summary the two buttons are stacked; along the bottom of a narrow window, side by
  // side (the dub on the right, where the eye ends).
  const actions = (row: boolean) => (
    <div className={row ? "flex flex-row-reverse gap-2" : "space-y-2"}>
      <Button
        className={row ? "min-w-0 flex-1" : "w-full"}
        loading={submit.isPending && submit.variables === null}
        disabled={!canRun}
        onClick={() => submit.mutate(null)}
      >
        <Play />
        <span className="truncate">
          {submit.isPending && started.total > 1
            ? ts("starting", { done: started.done + 1, total: started.total })
            : config.subtitlesOnly
              ? tn("runSubtitles")
              : tn("run")}
        </span>
        {!submit.isPending && (
          <Kbd className="ml-1 hidden border-primary-foreground/20 bg-transparent text-primary-foreground/80 sm:inline-flex">
            {keyLabel(["Mod", "Enter"])}
          </Kbd>
        )}
      </Button>
      <Button
        variant="secondary"
        className={row ? "min-w-0 flex-1" : "w-full"}
        loading={submit.isPending && submit.variables !== null}
        disabled={!canRun}
        onClick={() => submit.mutate(PREVIEW_SECONDS)}
      >
        <Headphones />{" "}
        <span className="truncate">{tn("preview", { seconds: PREVIEW_SECONDS })}</span>
      </Button>
    </div>
  );

  const problems = [
    blocked,
    keyMissing && translator ? ts("needsKey", { name: translator.label }) : null,
    submit.isError ? (submit.error as Error).message : null,
  ].filter(Boolean) as string[];

  return (
    <div className="mx-auto grid max-w-[1180px] gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-8">
        <section aria-labelledby="studio-source" className="space-y-3">
          <h2 id="studio-source" className="sr-only">
            {ts("sectionSource")}
          </h2>
          <SourcePicker
            mode={urlMode ? "url" : "file"}
            onMode={setMode}
            urlAvailable={!!options.urlAvailable}
            files={files}
            onFiles={setFiles}
            url={url}
            onUrl={setUrl}
            durations={durations}
            inputRef={inputRef}
          />
        </section>

        <Section n={1} id="studio-target" title={ts("sectionTarget")}>
          <div className="space-y-2">
            <p className="text-ui-body font-medium">{ts("languages")}</p>
            <div role="group" aria-label={ts("languages")} className="flex flex-wrap gap-1.5">
              {options.languages.map((l) => {
                const on = config.targetLangs.includes(l.code);
                return (
                  <button
                    key={l.code}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleLang(l.code)}
                    className={cn(
                      "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-ui-body transition-colors duration-(--dur-1)",
                      on
                        ? "border-primary bg-brand-tint text-foreground"
                        : "border-border bg-surface-1 text-muted-foreground hover:border-border-strong hover:text-foreground",
                    )}
                  >
                    {on && <Check className="size-3.5 text-primary" aria-hidden />}
                    {langName(l.code)}
                    <span className="font-mono text-ui-mono text-fg-subtle">{l.code}</span>
                  </button>
                );
              })}
            </div>
            <p className="text-ui-small text-muted-foreground">{ts("languagesHint")}</p>
          </div>
          <div className="space-y-2">
            <p id="studio-output" className="text-ui-body font-medium">
              {tn("output")}
            </p>
            <SegmentedControl
              aria-labelledby="studio-output"
              value={config.subtitlesOnly ? "subtitles" : "dub"}
              onValueChange={(v) => set({ subtitlesOnly: v === "subtitles" })}
              items={[
                { value: "dub", label: tn("outputDub") },
                { value: "subtitles", label: tn("outputSubtitles") },
              ]}
            />
          </div>
        </Section>

        <Section n={2} id="studio-translation" title={ts("sectionTranslation")}>
          <ChoiceCards
            aria-labelledby="studio-translation"
            value={config.translator}
            onValueChange={(v) => set({ translator: v })}
            className="xl:grid-cols-3"
          >
            {options.translators.map((tr) => {
              const keyed = KEYED_TRANSLATORS.has(tr.id);
              const set_ = keyed ? hasKey(tr.id) : undefined;
              return (
                <ChoiceCard
                  key={tr.id}
                  value={tr.id}
                  title={tr.label}
                  description={description("translators", tr.id, tr.description)}
                  badges={
                    tr.offline ? (
                      <Badge variant="success">
                        <WifiOff /> {tn("offlineBadge")}
                      </Badge>
                    ) : keyed ? (
                      <Badge variant={set_ ? "success" : "warning"}>
                        <KeyRound /> {set_ ? ts("keySet") : ts("keyMissing")}
                      </Badge>
                    ) : undefined
                  }
                />
              );
            })}
          </ChoiceCards>
          {keyMissing && (
            <p className="text-ui-small text-warning">
              <Link href="/app/settings" className="underline underline-offset-2">
                {ts("addKey")}
              </Link>
            </p>
          )}
        </Section>

        {!config.subtitlesOnly && (
          <Section n={3} id="studio-voice" title={ts("sectionVoice")}>
            <ChoiceCards
              aria-labelledby="studio-voice"
              value={config.tts}
              onValueChange={(v) => set({ tts: v })}
              className="xl:grid-cols-3"
            >
              {/* What can be chosen first; what has to be installed after it. */}
              {[...options.ttsEngines]
                .sort((a, b) => Number(a.available === false) - Number(b.available === false))
                .map((e) => (
                  <ChoiceCard
                    key={e.id}
                    value={e.id}
                    title={e.label}
                    description={description("engines", e.id, e.description)}
                    disabled={e.available === false}
                    reason={
                      <Link href="/app/models" className="underline underline-offset-2">
                        {ts("installIt")}
                      </Link>
                    }
                    badges={
                      <>
                        {e.offline && (
                          <Badge variant="success">
                            <WifiOff /> {tn("offlineBadge")}
                          </Badge>
                        )}
                        {e.requiresVoiceSample && (
                          <Badge variant="neutral">
                            <Clone /> {ts("clones")}
                          </Badge>
                        )}
                        {e.id === "openai" && hasKey("openai") !== undefined && (
                          <Badge variant={hasKey("openai") ? "success" : "warning"}>
                            <KeyRound /> {hasKey("openai") ? ts("keySet") : ts("keyMissing")}
                          </Badge>
                        )}
                      </>
                    }
                  />
                ))}
            </ChoiceCards>

            {config.tts === "edge" && (
              <div className="space-y-2 rounded-lg border border-border bg-surface-1 p-3">
                {config.targetLangs.map((lang) => (
                  <div
                    key={lang}
                    className="grid items-center gap-2 sm:grid-cols-[180px_minmax(0,1fr)]"
                  >
                    <label htmlFor={`voice-${lang}`} className="text-ui-body text-muted-foreground">
                      {ts("voiceFor", { language: langName(lang) })}
                    </label>
                    <VoiceChoice
                      id={`voice-${lang}`}
                      engine="edge"
                      lang={lang}
                      value={config.edgeVoices[lang] ?? null}
                      onChange={(v) => set({ edgeVoices: { ...config.edgeVoices, [lang]: v } })}
                      autoLabel={tn("voiceAuto")}
                    />
                  </div>
                ))}
              </div>
            )}

            {config.tts === "openai" && (
              <div className="grid gap-3 rounded-lg border border-border bg-surface-1 p-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label
                    htmlFor="studio-openai-model"
                    className="text-ui-body text-muted-foreground"
                  >
                    {tn("openaiModel")}
                  </label>
                  <Select
                    id="studio-openai-model"
                    className="h-9"
                    value={config.openaiTtsModel}
                    onChange={(e) => set({ openaiTtsModel: e.target.value })}
                  >
                    {options.openaiTtsModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <label
                    htmlFor="studio-openai-voice"
                    className="text-ui-body text-muted-foreground"
                  >
                    {tn("openaiVoice")}
                  </label>
                  <Select
                    id="studio-openai-voice"
                    className="h-9"
                    value={config.openaiVoice}
                    onChange={(e) => set({ openaiVoice: e.target.value })}
                  >
                    {options.openaiVoices.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.label}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            )}

            {engine?.requiresVoiceSample && (
              <div className="space-y-2 rounded-lg border border-border bg-surface-1 p-3">
                <label htmlFor="studio-sample" className="text-ui-body text-muted-foreground">
                  {tn("voiceSample")}
                </label>
                <VoiceChoice
                  id="studio-sample"
                  engine={config.tts}
                  lang={config.targetLang}
                  value={config.voiceSample}
                  onChange={(v) => set({ voiceSample: v ?? undefined })}
                  autoLabel={tn("voiceFromVideo")}
                />
                <p className="text-ui-small text-muted-foreground">
                  {tn.rich("voiceSampleHint", {
                    voices: (chunks) => (
                      <Link href="/app/voices" className="text-primary hover:underline">
                        {chunks}
                      </Link>
                    ),
                  })}
                </p>
              </div>
            )}
          </Section>
        )}

        <Collapsible open={more} onOpenChange={setMore} asChild>
          <section aria-labelledby="studio-more" className="space-y-1">
            <CollapsibleTrigger className="group flex w-full items-center gap-2.5 text-left">
              <span
                aria-hidden
                className="flex size-5 items-center justify-center rounded-full border border-border-strong font-mono text-[11px] text-muted-foreground"
              >
                {config.subtitlesOnly ? 3 : 4}
              </span>
              <h2 id="studio-more" className="text-ui-section">
                {ts("sectionMore")}
              </h2>
              <span className="min-w-0 flex-1 truncate text-ui-small text-muted-foreground">
                {!more && moreSummary}
              </span>
              <ChevronDown
                aria-hidden
                className="size-4 text-muted-foreground transition-transform duration-(--dur-2) group-data-[state=open]:rotate-180"
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="divide-y divide-border rounded-lg border border-border bg-surface-1 px-4">
              <Row id="studio-whisper" label={tn("whisperModel")}>
                <Select
                  id="studio-whisper"
                  className="h-9 w-40"
                  value={config.whisperModel}
                  onChange={(e) => set({ whisperModel: e.target.value })}
                >
                  {options.whisperModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </Row>

              {!config.subtitlesOnly && options.diarizeAvailable && (
                <Row id="studio-diarize" label={tn("diarizeToggle")} hint={tn("diarizeHint")}>
                  <div className="flex items-center gap-2">
                    {config.diarize && (
                      <Input
                        type="number"
                        min={1}
                        aria-label={tn("numSpeakersPlaceholder")}
                        placeholder="#"
                        value={config.numSpeakers ?? ""}
                        onChange={(e) =>
                          set({
                            numSpeakers: e.target.value ? Number(e.target.value) : undefined,
                          })
                        }
                        className="h-8 w-16"
                      />
                    )}
                    <Switch
                      id="studio-diarize"
                      checked={!!config.diarize}
                      onCheckedChange={(on) => set({ diarize: on })}
                    />
                  </div>
                </Row>
              )}

              {!config.subtitlesOnly && (
                <Row
                  id="studio-separate"
                  label={tn("separateToggle")}
                  hint={options.separateAvailable ? tn("separateHint") : tn("separateInstall")}
                >
                  <Switch
                    id="studio-separate"
                    checked={!!config.separate}
                    disabled={!options.separateAvailable}
                    onCheckedChange={(on) => set({ separate: on })}
                  />
                </Row>
              )}

              <Row
                id="studio-subtitles"
                label={tn("subtitlesInVideo")}
                hint={config.subtitlesInVideo === "hard" ? tn("subtitlesHardHint") : undefined}
              >
                <Select
                  id="studio-subtitles"
                  className="h-9 w-56"
                  value={config.subtitlesInVideo ?? ""}
                  onChange={(e) =>
                    set({
                      subtitlesInVideo: (e.target.value ||
                        null) as ConfigChoice["subtitlesInVideo"],
                    })
                  }
                >
                  <option value="">
                    {config.subtitlesOnly ? tn("subtitlesFileOnly") : tn("subtitlesNone")}
                  </option>
                  <option value="soft">{tn("subtitlesSoft")}</option>
                  <option value="hard">{tn("subtitlesHard")}</option>
                </Select>
              </Row>

              <Row
                id="studio-review"
                label={config.subtitlesOnly ? tn("reviewToggleSubtitles") : tn("reviewToggle")}
                hint={config.subtitlesOnly ? tn("reviewHintSubtitles") : tn("reviewHint")}
              >
                <Switch
                  id="studio-review"
                  checked={!!config.review}
                  onCheckedChange={(on) => set({ review: on })}
                />
              </Row>
            </CollapsibleContent>
          </section>
        </Collapsible>

        <RecentDubs />
      </div>

      <aside aria-labelledby="studio-summary" className="lg:sticky lg:top-0 lg:self-start">
        <div className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
          <h2 id="studio-summary" className="text-ui-label uppercase text-muted-foreground">
            {ts("summary")}
          </h2>
          <dl className="space-y-1.5 text-ui-small">
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{ts("sectionSource")}</dt>
              <dd className="truncate text-right">
                {urlMode
                  ? url.trim()
                    ? (() => {
                        try {
                          return new URL(url.trim()).hostname;
                        } catch {
                          return url.trim();
                        }
                      })()
                    : "—"
                  : files.length
                    ? `${ts("videos", { count: files.length })}${totalSeconds ? ` · ${formatDuration(totalSeconds)}` : ""}`
                    : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{ts("languages")}</dt>
              <dd className="text-right">{config.targetLangs.map(langName).join(", ")}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{ts("sectionTranslation")}</dt>
              <dd className="text-right">{translator?.label ?? config.translator}</dd>
            </div>
            {!config.subtitlesOnly && (
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">{ts("sectionVoice")}</dt>
                <dd className="text-right">{engine?.label ?? config.tts}</dd>
              </div>
            )}
            {jobs > 1 && (
              <div className="flex justify-between gap-3 border-t border-border pt-1.5">
                <dt className="text-muted-foreground">=</dt>
                <dd className="font-medium">{ts("dubs", { count: jobs })}</dd>
              </div>
            )}
          </dl>

          <div className="space-y-2 border-t border-border pt-3">
            <p className="text-ui-label uppercase text-muted-foreground">{ts("plan")}</p>
            <PlannedPath config={config} />
          </div>

          {problems.length > 0 && (
            <ul className="space-y-1 text-ui-small text-warning" aria-live="polite">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}

          <div className="hidden lg:block">{actions(false)}</div>
          <p className="hidden text-ui-small text-muted-foreground lg:block">
            {tn("previewHint", { seconds: PREVIEW_SECONDS })}
          </p>
        </div>
      </aside>

      {/* Below lg the summary is in the flow; its two buttons stay at hand along the bottom. */}
      <div className="sticky bottom-0 -mx-4 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:-mx-8 md:px-8 lg:hidden">
        {actions(true)}
      </div>
    </div>
  );
}
