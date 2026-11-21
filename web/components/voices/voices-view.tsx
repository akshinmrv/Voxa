"use client";

import { useId, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Command } from "cmdk";
import { ArrowRight, Check, ChevronsUpDown, FileAudio, Search, Trash2, Upload } from "lucide-react";
import { addVoice, deleteVoice, getOptions, getVoiceLibrary } from "@/lib/api";
import { STUDIO_CHOICE_KEY, type ConfigChoice } from "@/lib/job-config";
import { useLanguageNames } from "@/lib/use-language-names";
import type { LanguageOption, VoiceOption } from "@/lib/types";
import { useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SegmentedControl } from "@/components/ui/segmented";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useDescribeVoice, useVoices } from "@/components/app/voice-picker";
import { BackendError, Loading } from "@/components/app/query-states";
import { Play } from "@/components/studio/voice-choice";
import { cn } from "@/lib/utils";

const ENGINES = ["edge", "piper", "openai"] as const;
type Engine = (typeof ENGINES)[number];
const ENGINE_LABEL: Record<Engine, string> = { edge: "Edge", piper: "Piper", openai: "OpenAI" };

/** A language, found by typing its name or code. */
function LanguagePicker({
  languages,
  value,
  onChange,
}: {
  languages: LanguageOption[];
  value: string;
  onChange: (code: string) => void;
}) {
  const t = useTranslations("App.voices");
  const names = useLanguageNames();
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          role="combobox"
          aria-expanded={open}
          // "Language" and the one chosen, as it shows: its name says both.
          aria-labelledby={`${id}-label ${id}-value`}
          className="w-56 justify-between"
        >
          <span id={`${id}-label`} className="sr-only">
            {t("language")}
          </span>
          <span id={`${id}-value`} className="truncate">
            {names(value, languages.find((l) => l.code === value)?.name ?? value)}
            <span className="ml-1.5 font-mono text-ui-mono text-muted-foreground">{value}</span>
          </span>
          <ChevronsUpDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-0">
        <Command>
          <div className="flex items-center gap-2 border-b border-border px-2.5">
            <Search className="size-4 text-fg-subtle" aria-hidden />
            <Command.Input
              placeholder={t("chooseLanguage")}
              className="h-9 flex-1 bg-transparent text-ui-body outline-none placeholder:text-fg-subtle"
            />
          </div>
          <Command.List className="max-h-72 overflow-y-auto p-1">
            <Command.Empty className="px-2 py-3 text-ui-small text-muted-foreground">
              {t("noLanguage")}
            </Command.Empty>
            {languages.map((l) => (
              <Command.Item
                key={l.code}
                value={`${names(l.code, l.name)} ${l.name} ${l.code}`}
                onSelect={() => {
                  onChange(l.code);
                  setOpen(false);
                }}
                className="flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-ui-body data-[selected=true]:bg-surface-2"
              >
                <Check
                  className={cn("size-4", l.code === value ? "text-primary" : "invisible")}
                  aria-hidden
                />
                <span className="flex-1 truncate">{names(l.code, l.name)}</span>
                <span className="font-mono text-ui-mono text-muted-foreground">{l.code}</span>
              </Command.Item>
            ))}
          </Command.List>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/** Start a dub in the Studio with this voice, keeping the Studio's other choices. */
function useInStudio() {
  const router = useRouter();
  return (engine: Engine, lang: string, voice: VoiceOption) => {
    let kept: ConfigChoice = {};
    try {
      kept = JSON.parse(window.sessionStorage.getItem(STUDIO_CHOICE_KEY) ?? "{}") as ConfigChoice;
    } catch {
      /* nothing kept */
    }
    const choice: ConfigChoice = {
      ...kept,
      tts: engine,
      targetLangs: [lang],
      ...(engine === "edge" ? { edgeVoices: { ...kept.edgeVoices, [lang]: voice.id } } : {}),
      ...(engine === "openai" ? { openaiVoice: voice.id } : {}),
    };
    try {
      window.sessionStorage.setItem(STUDIO_CHOICE_KEY, JSON.stringify(choice));
    } catch {
      /* the Studio opens with its own choices */
    }
    router.push("/app");
  };
}

function Catalogue({ languages }: { languages: LanguageOption[] }) {
  const t = useTranslations("App.voices");
  const locale = useLocale();
  const describe = useDescribeVoice();
  const inStudio = useInStudio();
  const [lang, setLang] = useState(
    languages.find((l) => l.code === locale)?.code ?? languages[0]?.code ?? "en",
  );
  const [engine, setEngine] = useState<Engine>("edge");
  const [find, setFind] = useState("");
  const query = useVoices(engine, lang);
  const all: VoiceOption[] = useMemo(() => query.data?.voices ?? [], [query.data]);
  const needle = find.trim().toLowerCase();
  const voices = needle
    ? all.filter((v) =>
        `${v.label} ${v.id} ${v.locale ?? ""} ${v.gender ?? ""}`.toLowerCase().includes(needle),
      )
    : all;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <LanguagePicker languages={languages} value={lang} onChange={setLang} />
        <SegmentedControl
          size="sm"
          aria-label={t("engine")}
          value={engine}
          onValueChange={setEngine}
          items={ENGINES.map((e) => ({ value: e, label: ENGINE_LABEL[e] }))}
        />
        {all.length > 8 && (
          <div className="relative w-full sm:w-56">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
              aria-hidden
            />
            <Input
              type="search"
              aria-label={t("findVoice")}
              placeholder={t("findVoice")}
              value={find}
              onChange={(e) => setFind(e.target.value)}
              className="h-8 pl-8 text-ui-body"
            />
          </div>
        )}
        {query.data && (
          <span className="text-ui-small text-fg-subtle">
            {t("count", { count: voices.length })}
          </span>
        )}
      </div>
      <p className="text-ui-small text-muted-foreground">{t(`${engine}Desc`)}</p>

      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <p className="text-ui-body text-warning">
          {t("loadFailed", { error: (query.error as Error).message })}
        </p>
      ) : voices.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-surface-1 px-4 py-8 text-center text-ui-body text-muted-foreground">
          {engine === "piper" ? t("piperNone") : t("none")}
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-surface-1">
          {voices.map((v) => (
            <li key={v.id} className="flex items-center gap-3 px-3 py-2">
              {query.data.listen && v.installed !== false ? (
                <Play
                  engine={engine}
                  voice={v.id}
                  lang={lang}
                  library={false}
                  label={t("listen")}
                />
              ) : (
                <span className="size-7 shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ui-body">
                  <span className="truncate font-medium">{describe(v)}</span>
                  {v.styles && <Badge variant="neutral">{t("styles")}</Badge>}
                </p>
                {v.id !== v.label && (
                  <p className="truncate font-mono text-ui-mono text-fg-subtle">{v.id}</p>
                )}
              </div>
              <Button size="xs" variant="ghost" onClick={() => inStudio(engine, lang, v)}>
                {t("useInStudio")} <ArrowRight />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const MB = 1024 * 1024;

/** The clips voices are cloned from: add one by dropping it, hear and remove them. */
function MyVoices() {
  const t = useTranslations("App.voices");
  const common = useTranslations("Common");
  const qc = useQueryClient();
  const library = useQuery({ queryKey: ["voiceLibrary"], queryFn: getVoiceLibrary });
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [over, setOver] = useState(false);
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["voiceLibrary"] });
    void qc.invalidateQueries({ queryKey: ["voices"] });
  };
  const add = useMutation({
    mutationFn: () => addVoice(file as File, name.trim()),
    onSuccess: () => {
      setFile(null);
      setName("");
      if (input.current) input.current.value = "";
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: deleteVoice,
    onSuccess: () => {
      setRemoving(null);
      refresh();
    },
  });

  function choose(f: File | undefined) {
    if (!f) return;
    setFile(f);
    // The file's name, until one is typed.
    if (!name.trim()) setName(f.name.replace(/\.[^.]+$/, "").slice(0, 60));
  }

  return (
    <div className="space-y-5">
      <p className="text-ui-small text-muted-foreground">{t("libraryDesc")}</p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          choose(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "space-y-4 rounded-lg border border-dashed p-4 transition-colors duration-(--dur-1)",
          over ? "border-primary bg-brand-tint" : "border-border-strong bg-surface-1",
        )}
      >
        <div className="flex flex-wrap items-center gap-3">
          <Upload className="size-5 text-muted-foreground" aria-hidden />
          {file ? (
            <span className="inline-flex min-w-0 items-center gap-2 text-ui-body">
              <FileAudio className="size-4 shrink-0 text-primary" aria-hidden />
              <span className="truncate">{file.name}</span>
              <span className="text-fg-subtle">· {(file.size / MB).toFixed(1)} MB</span>
            </span>
          ) : (
            <span className="text-ui-body text-muted-foreground">{t("drop")}</span>
          )}
          <Button size="sm" variant="secondary" onClick={() => input.current?.click()}>
            {file ? t("chooseAnother") : t("choose")}
          </Button>
          <input
            ref={input}
            type="file"
            accept="audio/*,video/*"
            className="sr-only"
            tabIndex={-1}
            aria-label={t("file")}
            onChange={(e) => choose(e.target.files?.[0])}
          />
        </div>
        <p className="text-ui-small text-muted-foreground">{t("fileHint")}</p>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) add.mutate();
          }}
        >
          <label className="min-w-48 flex-1 space-y-1.5">
            <span className="block text-ui-small text-muted-foreground">{t("name")}</span>
            <Input
              value={name}
              maxLength={60}
              placeholder={t("namePlaceholder")}
              onChange={(e) => setName(e.target.value)}
              className="h-8 text-ui-body"
            />
          </label>
          <Button type="submit" size="sm" disabled={!file} loading={add.isPending}>
            {t("add")}
          </Button>
        </form>
        {add.isError && <p className="text-ui-small text-danger">{(add.error as Error).message}</p>}
      </div>

      {library.isPending ? (
        <Loading />
      ) : !library.data?.voices.length ? (
        <p className="text-ui-body text-muted-foreground">{t("libraryEmpty")}</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-surface-1">
          {library.data.voices.map((v) => (
            <li key={v.id} className="flex items-center gap-3 px-3 py-2">
              <Play engine="library" voice={v.id} lang="" library label={t("listen")} />
              <span className="min-w-0 flex-1 truncate text-ui-body font-medium">{v.name}</span>
              <span className="font-mono text-ui-mono text-muted-foreground">
                {t("seconds", { n: v.seconds })}
              </span>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`${t("delete")}: ${v.name}`}
                onClick={() => setRemoving({ id: v.id, name: v.name })}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteTitle", { name: removing?.name ?? "" })}</AlertDialogTitle>
            <AlertDialogDescription>{t("deleteConfirm")}</AlertDialogDescription>
          </AlertDialogHeader>
          {remove.isError && (
            <p className="text-ui-small text-danger">{(remove.error as Error).message}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive
              disabled={remove.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (removing) remove.mutate(removing.id);
              }}
            >
              {t("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/**
 * Voices (VOXA_DESIGN_PLAN.md §8.6): the catalogue of a language's voices by engine, to hear
 * and start a dub with; and the clips voices are cloned from. The tab is in the address
 * (?tab=mine), so the Studio links straight to the clips.
 */
export function VoicesView() {
  const t = useTranslations("App.voices");
  const params = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") === "mine" ? "mine" : "catalogue");
  const options = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const library = useQuery({ queryKey: ["voiceLibrary"], queryFn: getVoiceLibrary });

  if (options.isPending) return <Loading />;
  if (options.isError || !options.data) return <BackendError onRetry={() => options.refetch()} />;

  return (
    <Tabs
      value={tab}
      onValueChange={(next) => {
        setTab(next);
        window.history.replaceState(null, "", `?tab=${next}`);
      }}
      className="max-w-4xl"
    >
      <TabsList>
        <TabsTrigger value="catalogue">{t("catalogue")}</TabsTrigger>
        <TabsTrigger value="mine">
          {t("library")}
          {library.data?.voices.length ? (
            <span className="ml-1.5 text-fg-subtle">{library.data.voices.length}</span>
          ) : null}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="catalogue">
        <Catalogue languages={options.data.languages} />
      </TabsContent>
      <TabsContent value="mine">
        <MyVoices />
      </TabsContent>
    </Tabs>
  );
}
