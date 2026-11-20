"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Command } from "cmdk";
import { Check, ChevronsUpDown, Loader2, Search, Volume2 } from "lucide-react";
import { listenToVoice, voiceAudioUrl } from "@/lib/api";
import type { VoiceOption } from "@/lib/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useVoices } from "@/components/app/voice-picker";
import { cn } from "@/lib/utils";

// One voice at a time: a new one stops the last.
let playing: HTMLAudioElement | null = null;

/** ▶ for one voice: a library clip as it is, an Edge or Piper voice saying a line. */
export function Play({
  engine,
  voice,
  lang,
  library,
  label,
}: {
  engine: string;
  voice: string;
  lang: string;
  library: boolean;
  label: string;
}) {
  const play = useMutation({
    mutationFn: async () => {
      const src = library
        ? voiceAudioUrl(voice)
        : URL.createObjectURL(await listenToVoice({ engine, voice, lang }));
      playing?.pause();
      playing = new Audio(src);
      await playing.play();
    },
  });
  return (
    <button
      type="button"
      aria-label={`${label}: ${voice}`}
      title={play.isError ? (play.error as Error).message : label}
      // A row's own click chooses it; this one only plays.
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => {
        e.stopPropagation();
        play.mutate();
      }}
      className={cn(
        "inline-flex size-7 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-3 hover:text-primary [&_svg]:size-4",
        play.isError && "text-warning",
      )}
    >
      {play.isPending ? <Loader2 className="animate-spin" /> : <Volume2 />}
    </button>
  );
}

function describe(voice: VoiceOption, t: (key: string, values?: Record<string, number>) => string) {
  return [
    voice.gender === "male" || voice.gender === "female" ? t(voice.gender) : voice.gender,
    voice.locale,
    voice.installed === false ? t("notDownloaded") : null,
    voice.seconds ? t("seconds", { n: voice.seconds }) : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * Choose one of an engine's voices for a language, hearing any first, by typing a few letters
 * of its name, gender or locale. The empty choice, `autoLabel`, is Voxa's own: the voice it
 * picks, or for a cloning engine one cut from the video.
 */
export function VoiceChoice({
  id,
  engine,
  lang,
  value,
  onChange,
  autoLabel,
  disabled,
}: {
  id: string;
  engine: string;
  lang: string;
  value: string | null | undefined;
  onChange: (voice: string | null) => void;
  autoLabel: string;
  /** Can't be changed now (the job is being voiced). */
  disabled?: boolean;
}) {
  const t = useTranslations("App.voices");
  const ts = useTranslations("App.studio");
  const [open, setOpen] = useState(false);
  const query = useVoices(engine, lang);
  const voices = query.data?.voices ?? [];
  const library = !!query.data?.library;
  const audible = (v?: VoiceOption) =>
    !!v && (library || (!!query.data?.listen && v.installed !== false));
  const chosen = voices.find((v) => v.id === value);
  const pick = (voice: string | null) => {
    onChange(voice);
    setOpen(false);
  };

  return (
    <div className="flex items-center gap-1.5">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          id={id}
          disabled={disabled || query.isPending}
          className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-sm border border-input bg-surface-1 px-3 text-left text-ui-body transition-colors duration-(--dur-1) hover:border-border-strong disabled:opacity-50"
        >
          {query.isPending ? (
            <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
          ) : null}
          <span className="min-w-0 flex-1 truncate">
            {chosen ? chosen.label : value || autoLabel}
            {chosen && (
              <>
                {" "}
                <span className="ml-1 text-ui-small text-muted-foreground">
                  {describe(chosen, t)}
                </span>
              </>
            )}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        </PopoverTrigger>
        <PopoverContent className="w-[min(26rem,calc(100vw-2rem))] p-0" align="start">
          <Command loop>
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <Command.Input
                placeholder={ts("searchVoices")}
                className="h-10 flex-1 bg-transparent text-ui-body outline-none placeholder:text-fg-subtle"
              />
            </div>
            <Command.List className="max-h-72 overflow-y-auto p-1">
              <Command.Empty className="py-6 text-center text-ui-small text-muted-foreground">
                {ts("noVoices")}
              </Command.Empty>
              <Command.Item
                value={`auto ${autoLabel}`}
                onSelect={() => pick(null)}
                className="flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-ui-body outline-none data-[selected=true]:bg-surface-2"
              >
                <Check
                  className={cn("size-4 text-primary", value ? "invisible" : "")}
                  aria-hidden
                />
                {autoLabel}
              </Command.Item>
              {voices.map((v) => (
                <Command.Item
                  key={v.id}
                  value={`${v.id} ${v.label} ${describe(v, t)}`}
                  onSelect={() => pick(v.id)}
                  className="flex cursor-default items-center gap-2 rounded-sm px-2 py-1 text-ui-body outline-none data-[selected=true]:bg-surface-2"
                >
                  <Check
                    className={cn(
                      "size-4 shrink-0 text-primary",
                      v.id === value ? "" : "invisible",
                    )}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{v.label}</span>
                    <span className="block truncate text-ui-small text-muted-foreground">
                      {describe(v, t)}
                      {v.styles && ` · ${ts("styles")}`}
                    </span>
                  </span>
                  {audible(v) && (
                    <Play
                      engine={engine}
                      voice={v.id}
                      lang={lang}
                      library={library}
                      label={t("listen")}
                    />
                  )}
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </PopoverContent>
      </Popover>
      {chosen && audible(chosen) && (
        <Play engine={engine} voice={chosen.id} lang={lang} library={library} label={t("listen")} />
      )}
      {query.isError && (
        <p className="text-ui-small text-warning">
          {t("loadFailed", { error: (query.error as Error).message })}
        </p>
      )}
    </div>
  );
}
