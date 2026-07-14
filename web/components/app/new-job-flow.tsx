"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Play, WifiOff, KeyRound, Loader2 } from "lucide-react";
import type { JobConfig } from "@/lib/types";
import { getOptions, uploadVideo, createJob } from "@/lib/api";
import { useRouter } from "@/i18n/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { UploadDropzone } from "./upload-dropzone";
import { BackendError, Loading } from "./query-states";

const KEY_TRANSLATORS = new Set(["openai", "anthropic"]);

export function NewJobFlow() {
  const t = useTranslations("App.newJob");
  const router = useRouter();
  const optionsQuery = useQuery({ queryKey: ["options"], queryFn: getOptions });

  const [file, setFile] = useState<File | null>(null);
  const [sel, setSel] = useState<Partial<JobConfig>>({});

  const submit = useMutation({
    mutationFn: async (config: JobConfig) => {
      if (!file) throw new Error("No file");
      const { fileId } = await uploadVideo(file);
      const { jobId } = await createJob(fileId, config);
      return jobId;
    },
    onSuccess: (jobId) => router.push(`/app/jobs/${jobId}`),
  });

  if (optionsQuery.isPending) return <Loading />;
  if (optionsQuery.isError || !optionsQuery.data)
    return <BackendError onRetry={() => optionsQuery.refetch()} />;

  const options = optionsQuery.data;
  const set = <K extends keyof JobConfig>(key: K, value: JobConfig[K]) =>
    setSel((s) => ({ ...s, [key]: value }));

  // Effective config: user selection, falling back to the first available option.
  const config: JobConfig = {
    targetLang: sel.targetLang ?? options.languages[0]?.code ?? "en",
    translator: sel.translator ?? options.translators[0]?.id ?? "google",
    tts: sel.tts ?? options.ttsEngines[0]?.id ?? "edge",
    whisperModel: sel.whisperModel ?? "base",
    voiceSample: sel.voiceSample,
    openaiTtsModel: sel.openaiTtsModel ?? options.openaiTtsModels[0]?.id ?? "gpt-4o-mini-tts",
    openaiVoice: sel.openaiVoice ?? options.openaiVoices[0]?.id ?? "alloy",
  };

  const selectedTts = options.ttsEngines.find((e) => e.id === config.tts);
  const selectedTranslator = options.translators.find((e) => e.id === config.translator);
  const needsVoiceSample = selectedTts?.requiresVoiceSample ?? false;

  return (
    <div className="grid max-w-4xl gap-6 lg:grid-cols-5">
      <div className="lg:col-span-3">
        <UploadDropzone file={file} onFile={setFile} />
      </div>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>{t("configTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <Field id="targetLang" label={t("targetLang")}>
            <Select
              id="targetLang"
              value={config.targetLang}
              onChange={(e) => set("targetLang", e.target.value)}
            >
              {options.languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
            </Select>
          </Field>

          <Field id="translator" label={t("translator")}>
            <Select
              id="translator"
              value={config.translator}
              onChange={(e) => set("translator", e.target.value)}
            >
              {options.translators.map((tr) => (
                <option key={tr.id} value={tr.id}>
                  {tr.label} — {tr.description}
                </option>
              ))}
            </Select>
            <div className="flex gap-2">
              {selectedTranslator?.offline && (
                <Badge variant="success">
                  <WifiOff /> {t("offlineBadge")}
                </Badge>
              )}
              {KEY_TRANSLATORS.has(config.translator) && (
                <Badge variant="warning">
                  <KeyRound /> {t("keyBadge")}
                </Badge>
              )}
            </div>
          </Field>

          <Field id="tts" label={t("tts")}>
            <Select
              id="tts"
              value={config.tts}
              onChange={(e) => set("tts", e.target.value)}
            >
              {options.ttsEngines.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.label} — {e.description}
                </option>
              ))}
            </Select>
            {selectedTts?.offline && (
              <div>
                <Badge variant="success">
                  <WifiOff /> {t("offlineBadge")}
                </Badge>
              </div>
            )}
          </Field>

          {config.tts === "openai" && (
            <>
              <Field id="openaiTtsModel" label={t("openaiModel")}>
                <Select
                  id="openaiTtsModel"
                  value={config.openaiTtsModel}
                  onChange={(e) => set("openaiTtsModel", e.target.value)}
                >
                  {options.openaiTtsModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field id="openaiVoice" label={t("openaiVoice")}>
                <Select
                  id="openaiVoice"
                  value={config.openaiVoice}
                  onChange={(e) => set("openaiVoice", e.target.value)}
                >
                  {options.openaiVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}

          {needsVoiceSample && (
            <Field id="voiceSample" label={t("voiceSample")} hint={t("voiceSampleHint")}>
              <input
                id="voiceSample"
                type="text"
                placeholder="me.wav"
                value={config.voiceSample ?? ""}
                onChange={(e) => set("voiceSample", e.target.value)}
                className="h-10 w-full rounded-sm border border-input bg-surface-1 px-3 text-sm text-foreground transition-colors hover:border-primary/40 placeholder:text-fg-subtle"
              />
            </Field>
          )}

          <Field id="whisperModel" label={t("whisperModel")}>
            <Select
              id="whisperModel"
              value={config.whisperModel}
              onChange={(e) => set("whisperModel", e.target.value)}
            >
              {options.whisperModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>

          <div className="pt-1">
            <Button
              className="w-full"
              disabled={!file || submit.isPending}
              onClick={() => submit.mutate(config)}
            >
              {submit.isPending ? <Loader2 className="animate-spin" /> : <Play />}
              {t("run")}
            </Button>
            {!file && (
              <p className="mt-2 text-center text-xs text-muted-foreground">
                {t("runHint")}
              </p>
            )}
            {submit.isError && (
              <p className="mt-2 text-center text-xs text-danger">
                {(submit.error as Error).message}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
