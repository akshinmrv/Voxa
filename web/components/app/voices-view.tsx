"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { addVoice, deleteVoice, getOptions, getVoiceLibrary } from "@/lib/api";
import type { VoiceOption } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { ListenButton, useDescribeVoice, useVoices } from "./voice-picker";
import { BackendError, Loading } from "./query-states";

/** One engine's voices for the language, each to hear when the engine allows it. */
function EngineVoices({
  engine,
  lang,
  title,
  description,
  empty,
}: {
  engine: string;
  lang: string;
  title: string;
  description: string;
  empty: string;
}) {
  const t = useTranslations("App.voices");
  const describe = useDescribeVoice();
  const query = useVoices(engine, lang);
  const voices: VoiceOption[] = query.data?.voices ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {query.isPending ? (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        ) : query.isError ? (
          <p className="text-sm text-warning">
            {t("loadFailed", { error: (query.error as Error).message })}
          </p>
        ) : voices.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="divide-y divide-border">
            {voices.map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm text-foreground">{describe(v)}</span>
                  {v.id !== v.label && (
                    <span className="block truncate font-mono text-xs text-fg-subtle">{v.id}</span>
                  )}
                </span>
                {query.data.listen && v.installed !== false && (
                  <ListenButton engine={engine} voice={v.id} lang={lang} />
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** The clips voices are cloned from: add, hear and remove them. */
function VoiceLibrary() {
  const t = useTranslations("App.voices");
  const qc = useQueryClient();
  const library = useQuery({ queryKey: ["voiceLibrary"], queryFn: getVoiceLibrary });
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [inputKey, setInputKey] = useState(0);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["voiceLibrary"] });
    void qc.invalidateQueries({ queryKey: ["voices"] });
  };
  const add = useMutation({
    mutationFn: () => addVoice(file as File, name),
    onSuccess: () => {
      setFile(null);
      setName("");
      setInputKey((k) => k + 1);
      refresh();
    },
  });
  const remove = useMutation({ mutationFn: deleteVoice, onSuccess: refresh });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("library")}</CardTitle>
        <CardDescription>{t("libraryDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field id="voiceFile" label={t("file")} hint={t("fileHint")}>
            <input
              key={inputKey}
              id="voiceFile"
              type="file"
              accept="audio/*,video/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-sm file:border file:border-border file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:text-secondary-foreground"
            />
          </Field>
          <Field id="voiceName" label={t("name")}>
            <input
              id="voiceName"
              value={name}
              maxLength={60}
              placeholder={t("namePlaceholder")}
              onChange={(e) => setName(e.target.value)}
              className="h-10 w-full rounded-sm border border-input bg-surface-1 px-3 text-sm text-foreground transition-colors hover:border-primary/40 placeholder:text-fg-subtle"
            />
          </Field>
          <Button onClick={() => add.mutate()} disabled={!file || add.isPending}>
            {add.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
            {t("add")}
          </Button>
        </div>
        {add.isError && <p className="text-sm text-danger">{(add.error as Error).message}</p>}

        {library.isPending ? (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        ) : !library.data?.voices.length ? (
          <p className="text-sm text-muted-foreground">{t("libraryEmpty")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {library.data.voices.map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-3 py-2">
                <span className="min-w-0 truncate text-sm text-foreground">
                  {v.name} · {t("seconds", { n: v.seconds })}
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <ListenButton engine="library" voice={v.id} lang="" library />
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t("delete")}
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm(t("deleteConfirm", { name: v.name }))) remove.mutate(v.id);
                    }}
                  >
                    <Trash2 />
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function VoicesView() {
  const t = useTranslations("App.voices");
  const locale = useLocale();
  const options = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const [picked, setPicked] = useState<string | null>(null);

  if (options.isPending) return <Loading />;
  if (options.isError) return <BackendError onRetry={() => options.refetch()} />;
  const languages = options.data.languages;
  const lang =
    picked ?? languages.find((l) => l.code === locale)?.code ?? languages[0]?.code ?? "en";

  return (
    <div className="max-w-3xl space-y-6">
      <Field id="voicesLang" label={t("language")}>
        <Select id="voicesLang" value={lang} onChange={(e) => setPicked(e.target.value)}>
          {languages.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name} ({l.code})
            </option>
          ))}
        </Select>
      </Field>
      <EngineVoices
        engine="edge"
        lang={lang}
        title="Edge"
        description={t("edgeDesc")}
        empty={t("none")}
      />
      <EngineVoices
        engine="piper"
        lang={lang}
        title="Piper"
        description={t("piperDesc")}
        empty={t("piperNone")}
      />
      <EngineVoices
        engine="openai"
        lang={lang}
        title="OpenAI"
        description={t("openaiDesc")}
        empty={t("none")}
      />
      <VoiceLibrary />
    </div>
  );
}
