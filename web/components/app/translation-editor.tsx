"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { AudioLines, Check, Loader2 } from "lucide-react";
import { getTranslation, putJobVoices, putTranslation, voiceJob } from "@/lib/api";
import type { JobConfig, JobStatus, TranslationLine } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Loading } from "./query-states";
import { VoicePicker, useVoices } from "./voice-picker";
import { Field } from "@/components/ui/field";

/** As the server keeps a line: its words with the spacing evened out. */
const tidy = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

/** The voice a job speaks with for its engine, as its settings hold it. */
function ownVoice(config: JobConfig, library: boolean): string | null {
  if (config.tts === "edge") return config.edgeVoice ?? null;
  if (config.tts === "openai") return config.openaiVoice ?? null;
  return library ? (config.voiceSample ?? null) : null;
}

const sameVoices = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys(a).length === Object.keys(b).length && Object.keys(a).every((k) => a[k] === b[k]);

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

/**
 * A job's translated lines, each under the line it came from, to change before they are voiced
 * (a job waiting for review) or to change and voice again (a finished one: only the changed
 * lines are voiced again). Only the words can change; each line keeps its time.
 */
export function TranslationEditor({
  jobId,
  status,
  config,
  onVoice,
}: {
  jobId: string;
  status: JobStatus;
  /** The job's settings: its engine, language and voices. */
  config: JobConfig;
  /** Called once the job is queued to be voiced. */
  onVoice: () => void;
}) {
  const t = useTranslations("App.review");
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["translation", jobId],
    queryFn: () => getTranslation(jobId),
  });
  // Only the lines typed into are held here; the rest show what the server keeps.
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  // Voices chosen here and not saved yet (undefined: as the job has them).
  const [voiceDraft, setVoiceDraft] = useState<string | null | undefined>(undefined);
  const [speakerDraft, setSpeakerDraft] = useState<Record<string, string> | undefined>();
  const library = !!useVoices(config.tts, config.targetLang).data?.library;

  const lines: TranslationLine[] = query.data?.lines ?? [];
  const texts = lines.map((line, i) => drafts[i] ?? line.text);
  const unsaved = lines.filter((line, i) => drafts[i] !== undefined && tidy(drafts[i]) !== line.text)
    .length;
  const nothingToSay = texts.every((text) => !tidy(text));

  // Each speaker once, in the order they first speak, with the first thing they say.
  const speakers: [string, string][] = [];
  lines.forEach((line, i) => {
    if (line.speaker && !speakers.some(([s]) => s === line.speaker))
      speakers.push([line.speaker, tidy(texts[i])]);
  });
  // A line names its speaker as the voices above do ("Speaker 2"), not by pyannote's id
  // (SPEAKER_00), whose numbers needn't follow the order they speak in.
  const speakerNumber = new Map(speakers.map(([speaker], n) => [speaker, n + 1]));
  const savedVoice = ownVoice(config, library);
  const savedSpeakers = config.speakerVoices ?? {};
  const chosenVoice = voiceDraft === undefined ? savedVoice : voiceDraft;
  const speakerVoices = speakerDraft ?? savedSpeakers;
  const voicesChanged =
    (voiceDraft !== undefined && voiceDraft !== savedVoice) ||
    (speakerDraft !== undefined && !sameVoices(speakerDraft, savedSpeakers));
  const subtitlesOnly = !!config.subtitlesOnly;
  const pickable =
    !subtitlesOnly && (config.tts === "edge" || config.tts === "openai" || library);
  const autoLabel = library ? t("fromVideo") : config.tts === "piper" ? t("languageVoice") : t("voxaVoice");

  const save = useMutation({
    mutationFn: () => putTranslation(jobId, texts),
    onSuccess: (data) => {
      qc.setQueryData(["translation", jobId], data);
      setDrafts({});
    },
  });
  const voice = useMutation({
    mutationFn: async () => {
      if (voicesChanged) {
        await putJobVoices(jobId, { voice: chosenVoice, speakers: speakerVoices });
      }
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

  if (query.isPending) return <Loading />;
  if (query.isError) {
    return <p className="text-sm text-danger">{(query.error as Error).message}</p>;
  }
  const editable = query.data.editable && !voice.isPending;
  const reviewing = status === "review";
  const error = (save.error ?? voice.error) as Error | null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{reviewing ? t("title") : t("editTitle")}</CardTitle>
        <CardDescription>
          {subtitlesOnly
            ? reviewing
              ? t("descSubtitles")
              : t("editDescSubtitles")
            : reviewing
              ? t("desc")
              : t("editDesc")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!subtitlesOnly && (speakers.length > 0 || pickable) && (
          <div className="space-y-3 rounded-md border border-border bg-surface-1 p-4">
            <div>
              <p className="text-sm font-medium text-foreground">{t("voices")}</p>
              <p className="text-xs text-muted-foreground">{t("voicesHint")}</p>
            </div>
            {speakers.length > 0
              ? speakers.map(([speaker, line], n) => (
                  <Field key={speaker} id={`voice-${speaker}`} label={t("speaker", { n: n + 1 })}>
                    <VoicePicker
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
                      text={line || undefined}
                      disabled={!editable}
                    />
                  </Field>
                ))
              : pickable && (
                  <Field id="jobVoice" label={t("voice")}>
                    <VoicePicker
                      id="jobVoice"
                      engine={config.tts}
                      lang={config.targetLang}
                      value={chosenVoice}
                      onChange={(v) => setVoiceDraft(v)}
                      autoLabel={autoLabel}
                      text={tidy(texts.find((x) => tidy(x)) ?? "") || undefined}
                      disabled={!editable}
                    />
                  </Field>
                )}
          </div>
        )}

        <ol className="divide-y divide-border">
          {lines.map((line, i) => {
            const text = texts[i];
            const length = tidy(text).length;
            const long = length > line.maxChars;
            return (
              <li key={i} className="grid gap-2 py-3 first:pt-0 sm:grid-cols-[6.5rem_1fr]">
                <div className="flex flex-wrap items-start gap-2 pt-0.5 text-xs text-muted-foreground sm:flex-col">
                  <span className="tabular-nums">
                    {clock(line.start)}–{clock(line.end)}
                  </span>
                  {line.speaker && (
                    <Badge variant="neutral" title={line.speaker}>
                      {t("speaker", { n: speakerNumber.get(line.speaker) ?? 1 })}
                    </Badge>
                  )}
                </div>
                <div className="min-w-0 space-y-1.5">
                  {line.source && (
                    <p className="text-sm text-muted-foreground">{line.source}</p>
                  )}
                  <Textarea
                    rows={2}
                    value={text}
                    disabled={!editable}
                    aria-label={t("lineLabel", { n: i + 1 })}
                    onChange={(e) => setDrafts((d) => ({ ...d, [i]: e.target.value }))}
                  />
                  <p
                    className={cn(
                      "text-xs tabular-nums",
                      long ? "text-warning" : "text-fg-subtle",
                    )}
                  >
                    {length === 0
                      ? t("silent")
                      : long
                        ? t("long", { length, max: line.maxChars })
                        : t("fits", { length, max: line.maxChars })}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
          <Button
            onClick={() => voice.mutate()}
            disabled={!editable || nothingToSay || save.isPending}
          >
            {voice.isPending ? <Loader2 className="animate-spin" /> : <AudioLines />}
            {subtitlesOnly
              ? t("makeSubtitles")
              : reviewing
                ? t("voice")
                : t("voiceAgain")}
          </Button>
          <Button
            variant="secondary"
            onClick={() => save.mutate()}
            disabled={!editable || !unsaved || nothingToSay || save.isPending}
          >
            {save.isPending && <Loader2 className="animate-spin" />}
            {t("save")}
          </Button>
          {unsaved > 0 ? (
            <span className="text-sm text-muted-foreground">{t("unsaved", { count: unsaved })}</span>
          ) : (
            save.isSuccess && (
              <span className="inline-flex items-center gap-1.5 text-sm text-success">
                <Check className="size-4" /> {t("saved")}
              </span>
            )
          )}
          {nothingToSay && <span className="text-sm text-warning">{t("nothingToSay")}</span>}
          {error && <span className="text-sm text-danger">{error.message}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
