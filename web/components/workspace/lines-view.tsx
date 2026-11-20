"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AudioLines, Check, Play, Save, Search, Undo2 } from "lucide-react";
import {
  getTranslation,
  putJobVoices,
  putTranslation,
  resultVideoUrl,
  resultVttUrl,
  sourceVideoUrl,
  voiceJob,
} from "@/lib/api";
import type { JobConfig, JobStatus, TranslationLine } from "@/lib/types";
import { keyLabel } from "@/lib/shortcuts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { SegmentedControl } from "@/components/ui/segmented";
import { Tooltip } from "@/components/ui/tooltip";
import { LeaveDialog, useLeaveGuard } from "@/components/app/leave-guard";
import { Loading } from "@/components/app/query-states";
import { useVoices } from "@/components/app/voice-picker";
import { VoiceChoice } from "@/components/studio/voice-choice";
import { cn } from "@/lib/utils";

/** As the server keeps a line: its words with the spacing evened out. */
const tidy = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

/** 0:05.3: a line's place, to a tenth of a second. */
function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

/** 00:00:05.300, as WebVTT writes a time. */
function vttTime(seconds: number) {
  const ms = Math.round(seconds * 1000);
  const h = String(Math.floor(ms / 3600000)).padStart(2, "0");
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, "0");
  const s = String(Math.floor((ms % 60000) / 1000)).padStart(2, "0");
  return `${h}:${m}:${s}.${String(ms % 1000).padStart(3, "0")}`;
}

/** The voice a job speaks with for its engine, as its settings hold it. */
function ownVoice(config: JobConfig, library: boolean): string | null {
  if (config.tts === "edge") return config.edgeVoice ?? null;
  if (config.tts === "openai") return config.openaiVoice ?? null;
  return library ? (config.voiceSample ?? null) : null;
}

const sameVoices = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => a[k] === b[k]);

type Filter = "all" | "long" | "changed" | "empty";

/** A speaker's colour (--sp-1…6, round again past six), always beside their number. */
const speakerColor = (n: number) => `var(--sp-${((n - 1) % 6) + 1})`;

/** How a line's length sits in its time: under the budget, over it (spoken faster), silent. */
function FitMeter({ length, max }: { length: number; max: number }) {
  const t = useTranslations("App.review");
  const long = length > max;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <div className="h-[3px] w-24 shrink-0 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        {length === 0 ? (
          <div className="h-full w-full bg-[repeating-linear-gradient(90deg,var(--border-strong)_0_3px,transparent_3px_6px)]" />
        ) : (
          <div
            className={cn("h-full rounded-full", long ? "bg-warning" : "bg-primary/70")}
            style={{ width: `${Math.min(length / Math.max(max, 1), 1) * 100}%` }}
          />
        )}
      </div>
      <span className={cn("text-ui-small tabular", long ? "text-warning" : "text-fg-subtle")}>
        {length === 0
          ? t("silent")
          : long
            ? t("long", { length, max })
            : t("fits", { length, max })}
      </span>
    </div>
  );
}

/**
 * The lines, anchored (VOXA_DESIGN_PLAN.md §8.3): the video beside them and a timeline under,
 * all three in step. Playing marks the line being spoken and follows it; a line's time, or
 * its block on the timeline, takes the video there. Only the words change; each line keeps
 * its time. Changes are saved, then voiced (only the changed lines again), or voiced at once.
 */
export function LinesView({
  jobId,
  status,
  config,
  hasDub,
  hasSource,
  onVoice,
}: {
  jobId: string;
  status: JobStatus;
  config: JobConfig;
  /** The dubbed video is there to play. */
  hasDub: boolean;
  /** The original is there to play. */
  hasSource: boolean;
  /** Called once the job is queued to be voiced. */
  onVoice: () => void;
}) {
  const t = useTranslations("App.lines");
  const tr = useTranslations("App.review");
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["translation", jobId],
    queryFn: () => getTranslation(jobId),
  });

  // Only the lines typed into are held here; the rest show what the server keeps.
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [voiceDraft, setVoiceDraft] = useState<string | null | undefined>(undefined);
  const [speakerDraft, setSpeakerDraft] = useState<Record<string, string> | undefined>();
  const library = !!useVoices(config.tts, config.targetLang).data?.library;

  const [mode, setMode] = useState<"dub" | "original">(hasDub ? "dub" : "original");
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [speakerFilter, setSpeakerFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  // State, not a ref: the player appears only once the lines have loaded (or the source
  // switches), and its listeners have to be added to that element when it does.
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const playUntil = useRef<number | null>(null);
  const resume = useRef<{ at: number; play: boolean } | null>(null);

  const lines: TranslationLine[] = useMemo(() => query.data?.lines ?? [], [query.data]);
  const texts = lines.map((line, i) => drafts[i] ?? line.text);
  const changed = (i: number) => drafts[i] !== undefined && tidy(drafts[i]) !== lines[i].text;
  const unsaved = lines.filter((_, i) => changed(i)).length;
  const nothingToSay = lines.length > 0 && texts.every((text) => !tidy(text));

  // Each speaker once, in the order they first speak ("Speaker 1", "Speaker 2").
  const speakers: string[] = [];
  lines.forEach((line) => {
    if (line.speaker && !speakers.includes(line.speaker)) speakers.push(line.speaker);
  });
  const speakerNumber = (speaker: string) => speakers.indexOf(speaker) + 1;
  const savedVoice = ownVoice(config, library);
  const savedSpeakers = config.speakerVoices ?? {};
  const chosenVoice = voiceDraft === undefined ? savedVoice : voiceDraft;
  const speakerVoices = speakerDraft ?? savedSpeakers;
  const voicesChanged =
    (voiceDraft !== undefined && voiceDraft !== savedVoice) ||
    (speakerDraft !== undefined && !sameVoices(speakerDraft, savedSpeakers));
  const subtitlesOnly = !!config.subtitlesOnly;
  const pickable = !subtitlesOnly && (config.tts === "edge" || config.tts === "openai" || library);
  const autoLabel = library
    ? tr("fromVideo")
    : config.tts === "piper"
      ? tr("languageVoice")
      : tr("voxaVoice");
  const reviewing = status === "review";
  const dirty = unsaved > 0 || voicesChanged;

  const save = useMutation({
    mutationFn: () => putTranslation(jobId, texts),
    onSuccess: (data) => {
      qc.setQueryData(["translation", jobId], data);
      setDrafts({});
    },
  });
  const voice = useMutation({
    mutationFn: async () => {
      if (voicesChanged) await putJobVoices(jobId, { voice: chosenVoice, speakers: speakerVoices });
      if (unsaved) qc.setQueryData(["translation", jobId], await putTranslation(jobId, texts));
      return voiceJob(jobId);
    },
    onSuccess: (summary) => {
      setDrafts({});
      setVoiceDraft(undefined);
      setSpeakerDraft(undefined);
      qc.setQueryData(["job", jobId], summary);
      onVoice();
    },
  });
  const editable = !!query.data?.editable && !voice.isPending;

  // ── the player ───────────────────────────────────────
  const src =
    mode === "dub" && hasDub
      ? resultVideoUrl(jobId)
      : hasSource
        ? sourceVideoUrl(jobId)
        : hasDub
          ? resultVideoUrl(jobId)
          : null;
  const showingOriginal = src !== null && src === sourceVideoUrl(jobId);

  useEffect(() => {
    const v = videoEl;
    if (!v) return;
    let frame = 0;
    const tick = () => {
      // A tenth of a second is enough for the playhead and the line being spoken, and React
      // skips a render when the value is the same: at most ten a second, not one a frame.
      setTime(Math.round(v.currentTime * 10) / 10);
      if (playUntil.current !== null && v.currentTime >= playUntil.current) {
        v.pause();
        playUntil.current = null;
      }
      if (!v.paused) frame = requestAnimationFrame(tick);
    };
    const onPlay = () => {
      setPlaying(true);
      frame = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      setTime(v.currentTime);
    };
    const onSeeked = () => setTime(v.currentTime);
    const onMeta = () => {
      setDuration(Number.isFinite(v.duration) ? v.duration : 0);
      // Switched between the original and the dub: carry on from the same moment.
      if (resume.current) {
        v.currentTime = resume.current.at;
        if (resume.current.play) void v.play();
        resume.current = null;
      }
    };
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("seeked", onSeeked);
    v.addEventListener("loadedmetadata", onMeta);
    return () => {
      cancelAnimationFrame(frame);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("seeked", onSeeked);
      v.removeEventListener("loadedmetadata", onMeta);
    };
  }, [videoEl]);

  const seek = (at: number) => {
    const v = videoEl;
    if (!v) return;
    playUntil.current = null;
    v.currentTime = at;
    setTime(at);
  };
  const playLine = (i: number) => {
    const v = videoEl;
    const line = lines[i];
    if (!v || !line) return;
    v.currentTime = line.start;
    playUntil.current = line.end;
    void v.play();
  };
  const switchTo = (next: "dub" | "original") => {
    const v = videoEl;
    if (v) resume.current = { at: v.currentTime, play: !v.paused };
    setMode(next);
  };

  // The line being spoken now.
  const active = lines.findIndex((line) => time >= line.start && time < line.end);

  // The original under the lines as they read now, edits and all. Built from the text, not
  // the array (a new one each render), so a new track comes only when a line has changed.
  const vtt = useDeferredValue(
    `WEBVTT\n\n${lines
      .map((line, i) => [line, tidy(texts[i] ?? "")] as const)
      .filter(([, text]) => text)
      .map(([line, text]) => `${vttTime(line.start)} --> ${vttTime(line.end)}\n${text}`)
      .join("\n\n")}\n`,
  );
  const captions = useMemo(
    () =>
      typeof window === "undefined" || !lines.length
        ? null
        : URL.createObjectURL(new Blob([vtt], { type: "text/vtt" })),
    [vtt, lines.length],
  );
  useEffect(
    () => () => {
      if (captions) URL.revokeObjectURL(captions);
    },
    [captions],
  );

  // ── the list ─────────────────────────────────────────
  const needle = search.trim().toLowerCase();
  const visible = lines
    .map((_, i) => i)
    .filter((i) => {
      const length = tidy(texts[i]).length;
      if (filter === "long" && !(length > lines[i].maxChars)) return false;
      if (filter === "changed" && !changed(i)) return false;
      if (filter === "empty" && length !== 0) return false;
      if (speakerFilter && lines[i].speaker !== speakerFilter) return false;
      if (needle) {
        const hay = `${lines[i].source} ${texts[i]}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });

  // The React Compiler isn't on in this app (next.config.ts), so nothing memoizes the
  // virtualizer's functions: each render reads them afresh.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtual = useVirtualizer({
    count: visible.length,
    getScrollElement: () => list.current,
    estimateSize: () => 140,
    overscan: 6,
  });

  // While it plays, the list keeps the spoken line in view (unless you're typing in one).
  useEffect(() => {
    if (!playing || active < 0) return;
    if (document.activeElement instanceof HTMLTextAreaElement) return;
    const at = visible.indexOf(active);
    if (at >= 0) virtual.scrollToIndex(at, { align: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, playing]);

  const focusLine = (i: number) => {
    setSel(i);
    const at = visible.indexOf(i);
    if (at < 0) return;
    virtual.scrollToIndex(at, { align: "auto" });
    requestAnimationFrame(() =>
      requestAnimationFrame(() => document.getElementById(`line-${jobId}-${i}`)?.focus()),
    );
  };

  // ── keys (lib/shortcuts.ts lists them) ───────────────
  const noop = () => {};
  const keys = useRef<
    Record<"play" | "toggle" | "save" | "voice", () => void> & {
      step: (by: number) => void;
    }
  >({ step: noop, play: noop, toggle: noop, save: noop, voice: noop });
  useEffect(() => {
    keys.current = {
      step: (d) => {
        const at = visible.indexOf(sel);
        const next = visible[Math.min(Math.max((at < 0 ? 0 : at) + d, 0), visible.length - 1)];
        if (next !== undefined) focusLine(next);
      },
      play: () => playLine(sel),
      toggle: () => hasDub && hasSource && switchTo(mode === "dub" ? "original" : "dub"),
      save: () => editable && unsaved > 0 && !nothingToSay && save.mutate(),
      voice: () => editable && !nothingToSay && !save.isPending && voice.mutate(),
    };
  });
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const mod = event.ctrlKey || event.metaKey;
      if (event.altKey && !mod && !event.shiftKey) {
        const key = event.key.toLowerCase();
        const act =
          key === "arrowdown"
            ? () => keys.current.step(1)
            : key === "arrowup"
              ? () => keys.current.step(-1)
              : key === "p"
                ? keys.current.play
                : key === "o"
                  ? keys.current.toggle
                  : null;
        if (act) {
          event.preventDefault();
          act();
        }
      } else if (mod && !event.altKey && !event.shiftKey) {
        if (event.key.toLowerCase() === "s") {
          event.preventDefault();
          keys.current.save();
        } else if (event.key === "Enter") {
          event.preventDefault();
          keys.current.voice();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ── not losing what was typed ────────────────────────
  const guard = useLeaveGuard(dirty);

  if (query.isPending) return <Loading />;
  if (query.isError)
    return <p className="text-ui-small text-danger">{(query.error as Error).message}</p>;

  const total = Math.max(duration, lines.at(-1)?.end ?? 0, 1);
  const error = (save.error ?? voice.error) as Error | null;
  const filters: { value: Filter; label: string }[] = [
    { value: "all", label: t("filterAll") },
    { value: "long", label: t("filterLong") },
    { value: "changed", label: t("filterChanged") },
    { value: "empty", label: t("filterEmpty") },
  ];
  // Ticks along the timeline at a round step: 1, 2, 5, 10, 15, 30 s… about eight of them.
  const tick = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600].find((s) => total / s <= 10) ?? 600;

  return (
    <div className="space-y-4">
      {/* The timeline: every line where it falls, the playhead, a click to go there. */}
      <div className="space-y-1" aria-hidden>
        <div
          className="relative h-12 cursor-pointer overflow-hidden rounded-lg border border-border bg-surface-1"
          onClick={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            seek(((e.clientX - box.left) / box.width) * total);
          }}
        >
          {lines.map((line, i) => {
            const number = line.speaker ? speakerNumber(line.speaker) : 0;
            const empty = !tidy(texts[i]);
            const long = tidy(texts[i]).length > line.maxChars;
            const edge = empty
              ? "var(--border-strong)"
              : number
                ? speakerColor(number)
                : "var(--primary)";
            return (
              <button
                key={i}
                type="button"
                tabIndex={-1}
                title={`${clock(line.start)} ${tidy(texts[i])}`}
                onClick={(e) => {
                  e.stopPropagation();
                  seek(line.start);
                  focusLine(i);
                }}
                className={cn(
                  "absolute bottom-2 top-2 rounded-sm border",
                  i === sel && "ring-2 ring-ring",
                  empty &&
                    "bg-[repeating-linear-gradient(135deg,var(--border-strong)_0_2px,transparent_2px_5px)]",
                )}
                style={{
                  left: `${(line.start / total) * 100}%`,
                  width: `${Math.max(((line.end - line.start) / total) * 100, 0.4)}%`,
                  backgroundColor: empty
                    ? undefined
                    : `color-mix(in oklab, ${edge} ${i === active ? 55 : 28}%, transparent)`,
                  // Each side on its own: React clearing a side set over a shorthand would
                  // take the shorthand's colour with it. The bottom is amber for a line over
                  // its time.
                  borderTopColor: edge,
                  borderRightColor: edge,
                  borderLeftColor: edge,
                  borderBottomColor: long ? "var(--warning)" : edge,
                  borderBottomWidth: long ? 3 : 1,
                }}
              >
                {changed(i) && (
                  <span className="absolute -top-1 right-0.5 size-1.5 rounded-full bg-primary" />
                )}
              </button>
            );
          })}
          <span
            className="pointer-events-none absolute inset-y-0 w-0.5 bg-primary"
            style={{ left: `${(time / total) * 100}%` }}
          />
        </div>
        <div className="relative h-4 font-mono text-[10px] text-fg-subtle">
          {Array.from({ length: Math.floor(total / tick) + 1 }, (_, n) => n * tick).map((s) => (
            <span
              key={s}
              className="absolute -translate-x-1/2"
              style={{ left: `${(s / total) * 100}%` }}
            >
              {clock(s).replace(/\.0$/, "")}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* The player, and the voices the lines are spoken with. */}
        <div className="space-y-3 lg:sticky lg:top-0 lg:self-start">
          {src ? (
            <video
              ref={setVideoEl}
              key={src}
              controls
              crossOrigin="anonymous"
              preload="metadata"
              className="aspect-video w-full rounded-lg border border-border bg-black"
              src={src}
            >
              {showingOriginal && captions ? (
                <track
                  key={captions}
                  kind="subtitles"
                  src={captions}
                  srcLang={config.targetLang}
                  label={t("captions")}
                  default
                />
              ) : (
                !showingOriginal &&
                config.subtitlesInVideo !== "hard" && (
                  <track
                    kind="subtitles"
                    src={resultVttUrl(jobId)}
                    srcLang={config.targetLang}
                    label={config.targetLang}
                    default={!!config.subtitlesOnly || config.subtitlesInVideo === "soft"}
                  />
                )
              )}
            </video>
          ) : (
            <p className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-border-strong p-6 text-center text-ui-small text-muted-foreground">
              {t("noVideo")}
            </p>
          )}
          {hasDub && hasSource && (
            <SegmentedControl
              size="sm"
              aria-label={`${t("dub")} / ${t("original")}`}
              value={mode}
              onValueChange={switchTo}
              items={[
                { value: "dub", label: t("dub") },
                { value: "original", label: t("original") },
              ]}
            />
          )}

          {!subtitlesOnly && (speakers.length > 0 || pickable) && (
            <section
              aria-labelledby="voices"
              className="space-y-2.5 rounded-lg border border-border bg-surface-1 p-3"
            >
              <div>
                <h3 id="voices" className="text-ui-section">
                  {tr("voices")}
                </h3>
                <p className="text-ui-small text-muted-foreground">{tr("voicesHint")}</p>
              </div>
              {speakers.length > 0
                ? speakers.map((speaker, n) => (
                    <div
                      key={speaker}
                      className="grid items-center gap-2 sm:grid-cols-[110px_minmax(0,1fr)]"
                    >
                      <label
                        htmlFor={`voice-${speaker}`}
                        className="flex items-center gap-2 text-ui-body"
                      >
                        <span
                          className="size-2.5 shrink-0 rounded-full"
                          style={{ background: speakerColor(n + 1) }}
                          aria-hidden
                        />
                        {tr("speaker", { n: n + 1 })}
                      </label>
                      <VoiceChoice
                        id={`voice-${speaker}`}
                        engine={config.tts}
                        lang={config.targetLang}
                        value={speakerVoices[speaker] ?? null}
                        onChange={(v) => {
                          const next = { ...speakerVoices };
                          if (v) next[speaker] = v;
                          else delete next[speaker];
                          setSpeakerDraft(next);
                        }}
                        autoLabel={autoLabel}
                        disabled={!editable}
                      />
                    </div>
                  ))
                : pickable && (
                    <VoiceChoice
                      id="job-voice"
                      engine={config.tts}
                      lang={config.targetLang}
                      value={chosenVoice}
                      onChange={(v) => setVoiceDraft(v)}
                      autoLabel={autoLabel}
                      disabled={!editable}
                    />
                  )}
            </section>
          )}
        </div>

        {/* The lines. */}
        <div className="min-w-0 rounded-lg border border-border bg-surface-1">
          <div className="flex flex-wrap items-center gap-2 border-b border-border p-2">
            <div className="relative min-w-40 flex-1">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
                aria-hidden
              />
              <Input
                aria-label={t("search")}
                placeholder={t("search")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 pl-8 text-ui-body"
              />
            </div>
            <SegmentedControl
              size="sm"
              aria-label={t("filterAll")}
              value={filter}
              onValueChange={setFilter}
              items={filters}
            />
            {speakers.length > 1 &&
              speakers.map((speaker, n) => (
                <button
                  key={speaker}
                  type="button"
                  aria-pressed={speakerFilter === speaker}
                  onClick={() => setSpeakerFilter((s) => (s === speaker ? null : speaker))}
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-ui-small transition-colors duration-(--dur-1)",
                    speakerFilter === speaker
                      ? "border-primary bg-brand-tint text-foreground"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  <span
                    className="size-2 rounded-full"
                    style={{ background: speakerColor(n + 1) }}
                    aria-hidden
                  />
                  {tr("speaker", { n: n + 1 })}
                </button>
              ))}
            <span className="ml-auto px-1 text-ui-small tabular text-fg-subtle">
              {t("count", { shown: visible.length, total: lines.length })}
            </span>
          </div>

          <div
            ref={list}
            className="h-[min(62vh,640px)] overflow-y-auto"
            role="list"
            aria-label={tr("title")}
          >
            {visible.length === 0 ? (
              <p className="p-6 text-center text-ui-small text-muted-foreground">{t("noMatch")}</p>
            ) : (
              <div className="relative w-full" style={{ height: virtual.getTotalSize() }}>
                {virtual.getVirtualItems().map((item) => {
                  const i = visible[item.index];
                  const line = lines[i];
                  const text = texts[i];
                  const isActive = i === active;
                  const number = line.speaker ? speakerNumber(line.speaker) : 0;
                  return (
                    <div
                      key={i}
                      role="listitem"
                      data-index={item.index}
                      ref={virtual.measureElement}
                      className="absolute left-0 top-0 w-full"
                      style={{ transform: `translateY(${item.start}px)` }}
                    >
                      <div
                        className={cn(
                          "relative flex gap-3 border-b border-border px-3 py-3 transition-colors duration-(--dur-1)",
                          isActive ? "bg-brand-tint" : sel === i ? "bg-surface-2/60" : "",
                        )}
                      >
                        {/* The anchor: the line being spoken now. */}
                        {isActive && (
                          <span
                            aria-hidden
                            className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary"
                          />
                        )}
                        <div className="w-[86px] shrink-0 space-y-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setSel(i);
                              seek(line.start);
                            }}
                            className="block font-mono text-ui-mono tabular text-foreground hover:text-primary"
                          >
                            {clock(line.start)}
                          </button>
                          <span className="block font-mono text-ui-mono tabular text-fg-subtle">
                            {clock(line.end)}
                          </span>
                          {line.speaker && (
                            <span
                              className="flex items-center gap-1.5 text-ui-small text-muted-foreground"
                              title={line.speaker}
                            >
                              <span
                                className="size-2 shrink-0 rounded-full"
                                style={{ background: speakerColor(number) }}
                                aria-hidden
                              />
                              {tr("speaker", { n: number })}
                            </span>
                          )}
                          <Tooltip label={t("play")} shortcut={keyLabel(["Alt", "P"])}>
                            <Button
                              size="icon-sm"
                              variant="ghost"
                              aria-label={t("play")}
                              disabled={!src}
                              onClick={() => {
                                setSel(i);
                                playLine(i);
                              }}
                            >
                              <Play />
                            </Button>
                          </Tooltip>
                        </div>
                        <div className="min-w-0 flex-1 space-y-1.5">
                          {line.source && (
                            <p className="text-ui-small text-muted-foreground">{line.source}</p>
                          )}
                          <Textarea
                            id={`line-${jobId}-${i}`}
                            rows={2}
                            value={text}
                            disabled={!editable}
                            aria-label={tr("lineLabel", { n: i + 1 })}
                            onFocus={() => setSel(i)}
                            onChange={(e) => setDrafts((d) => ({ ...d, [i]: e.target.value }))}
                            className={cn("text-ui-editor", changed(i) && "border-primary/50")}
                          />
                          <FitMeter length={tidy(text).length} max={line.maxChars} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* What to do with the changes, always at hand. */}
      <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center gap-2 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:-mx-8 md:px-8">
        <Button
          onClick={() => voice.mutate()}
          disabled={!editable || nothingToSay || save.isPending}
          loading={voice.isPending}
        >
          <AudioLines />
          {subtitlesOnly ? tr("makeSubtitles") : reviewing ? tr("voice") : tr("voiceAgain")}
        </Button>
        <Button
          variant="secondary"
          onClick={() => save.mutate()}
          disabled={!editable || !unsaved || nothingToSay}
          loading={save.isPending}
        >
          <Save /> {tr("save")}
        </Button>
        {unsaved > 0 && (
          <Button variant="ghost" onClick={() => setDrafts({})} disabled={!editable}>
            <Undo2 /> {t("revert")}
          </Button>
        )}
        <span className="text-ui-small text-muted-foreground" aria-live="polite">
          {unsaved > 0 ? (
            tr("unsaved", { count: unsaved })
          ) : save.isSuccess ? (
            <span className="inline-flex items-center gap-1.5 text-success">
              <Check className="size-4" /> {tr("saved")}
            </span>
          ) : null}
        </span>
        {nothingToSay && <span className="text-ui-small text-warning">{tr("nothingToSay")}</span>}
        {error && <span className="text-ui-small text-danger">{error.message}</span>}
        <span className="ml-auto hidden text-ui-small text-fg-subtle xl:block">{t("keys")}</span>
      </div>

      <LeaveDialog
        guard={guard}
        title={t("leaveTitle")}
        body={t("leaveBody", { count: Math.max(unsaved, 1) })}
        stayLabel={t("stay")}
        leaveLabel={t("leave")}
        onForget={() => {
          setDrafts({});
          setVoiceDraft(undefined);
          setSpeakerDraft(undefined);
        }}
      />
    </div>
  );
}
