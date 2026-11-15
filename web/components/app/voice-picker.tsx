"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Loader2, Volume2 } from "lucide-react";
import { getVoices, listenToVoice, voiceAudioUrl } from "@/lib/api";
import type { VoiceOption } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

/** An engine's voices for a language, asked once (Edge's list comes from Microsoft). */
export function useVoices(engine: string, lang: string) {
  return useQuery({
    queryKey: ["voices", engine, lang],
    queryFn: () => getVoices(engine, lang),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

/** "Banu · female · az-AZ": what a person needs to tell the voices apart. */
export function useDescribeVoice() {
  const t = useTranslations("App.voices");
  return (voice: VoiceOption) =>
    [
      voice.label,
      voice.gender === "male" || voice.gender === "female" ? t(voice.gender) : voice.gender,
      voice.locale,
      voice.installed === false ? t("notDownloaded") : null,
      voice.seconds ? t("seconds", { n: voice.seconds }) : null,
    ]
      .filter(Boolean)
      .join(" · ");
}

/**
 * Plays one voice: a library clip as it is, an Edge or Piper voice saying `text` (a line of
 * the dub, or a greeting in its language when there's none).
 */
export function ListenButton({
  engine,
  voice,
  lang,
  text,
  library = false,
}: {
  engine: string;
  voice: string;
  lang: string;
  text?: string;
  library?: boolean;
}) {
  const t = useTranslations("App.voices");
  const play = useMutation({
    mutationFn: async () => {
      const src = library
        ? voiceAudioUrl(voice)
        : URL.createObjectURL(await listenToVoice({ engine, voice, lang, text }));
      await new Audio(src).play();
    },
  });
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        type="button"
        size="icon"
        variant="secondary"
        onClick={() => play.mutate()}
        disabled={play.isPending}
        aria-label={t("listen")}
        title={play.isError ? (play.error as Error).message : t("listen")}
      >
        {play.isPending ? <Loader2 className="animate-spin" /> : <Volume2 />}
      </Button>
      {play.isError && <span className="sr-only">{(play.error as Error).message}</span>}
    </span>
  );
}

/**
 * Choose a voice of one engine for a language, and hear it. The empty choice is Voxa's own
 * (`autoLabel`): the voice it picks, or for a cloning engine one cut from the video.
 */
export function VoicePicker({
  id,
  engine,
  lang,
  value,
  onChange,
  autoLabel,
  text,
  disabled,
}: {
  id: string;
  engine: string;
  lang: string;
  value: string | null | undefined;
  onChange: (voice: string | null) => void;
  autoLabel: string;
  text?: string;
  disabled?: boolean;
}) {
  const t = useTranslations("App.voices");
  const describe = useDescribeVoice();
  const query = useVoices(engine, lang);
  const voices = query.data?.voices ?? [];
  const chosen = voices.find((v) => v.id === value);
  const audible =
    !!value &&
    (query.data?.library || (query.data?.listen && chosen?.installed !== false));

  return (
    <div className="space-y-1">
      <div className="flex gap-2">
        <div className="min-w-0 flex-1">
          <Select
            id={id}
            value={value ?? ""}
            disabled={disabled || query.isPending}
            onChange={(e) => onChange(e.target.value || null)}
          >
            <option value="">{autoLabel}</option>
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {describe(v)}
              </option>
            ))}
            {value && !chosen && !query.isPending && <option value={value}>{value}</option>}
          </Select>
        </div>
        {audible && (
          <ListenButton
            engine={engine}
            voice={value}
            lang={lang}
            text={text}
            library={!!query.data?.library}
          />
        )}
      </div>
      {query.isError && (
        <p className="text-xs text-warning">
          {t("loadFailed", { error: (query.error as Error).message })}
        </p>
      )}
    </div>
  );
}
