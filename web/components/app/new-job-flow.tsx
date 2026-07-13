"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Play, WifiOff, KeyRound, CheckCircle2 } from "lucide-react";
import type { JobConfig, VoxaOptions } from "@/lib/types";
import { buildCommand } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { UploadDropzone } from "./upload-dropzone";

const KEY_TRANSLATORS = new Set(["openai", "anthropic"]);

export function NewJobFlow({ options }: { options: VoxaOptions }) {
  const t = useTranslations("App.newJob");
  const [file, setFile] = useState<File | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [config, setConfig] = useState<JobConfig>({
    targetLang: options.languages[0]?.code ?? "en",
    translator: options.translators[0]?.id ?? "google",
    tts: options.ttsEngines[0]?.id ?? "edge",
    whisperModel: "base",
  });

  const set = <K extends keyof JobConfig>(key: K, value: JobConfig[K]) =>
    setConfig((c) => ({ ...c, [key]: value }));

  const selectedTts = options.ttsEngines.find((e) => e.id === config.tts);
  const selectedTranslator = options.translators.find(
    (e) => e.id === config.translator,
  );
  const needsVoiceSample = selectedTts?.requiresVoiceSample ?? false;

  if (submitted && file) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="flex items-start gap-3 rounded-md border border-success/25 bg-success/10 p-4">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" />
          <div>
            <p className="font-medium">{t("queuedTitle")}</p>
            <p className="mt-1 text-sm text-muted-foreground">{t("queuedBody")}</p>
          </div>
        </div>
        <TerminalBlock command={buildCommand(file.name, config)} />
        <Button
          variant="secondary"
          onClick={() => {
            setSubmitted(false);
            setFile(null);
          }}
        >
          {t("reset")}
        </Button>
      </div>
    );
  }

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

          {needsVoiceSample && (
            <Field
              id="voiceSample"
              label={t("voiceSample")}
              hint={t("voiceSampleHint")}
            >
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
              disabled={!file}
              onClick={() => setSubmitted(true)}
            >
              <Play /> {t("run")}
            </Button>
            {!file && (
              <p className="mt-2 text-center text-xs text-muted-foreground">
                {t("runHint")}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
