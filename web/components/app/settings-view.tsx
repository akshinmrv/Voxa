"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Check, Loader2, RotateCcw } from "lucide-react";
import {
  getOptions,
  getSettings,
  updateSettings,
  resetSettings,
  getKeys,
} from "@/lib/api";
import type { SettingsPatch } from "@/lib/types";
import { AppPageHeader } from "@/components/app/app-page-header";
import { BackendError, Loading } from "@/components/app/query-states";
import { ProviderCard } from "@/components/app/provider-card";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";

export function SettingsView() {
  const t = useTranslations("App.settings");
  const qc = useQueryClient();

  const optionsQuery = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const keysQuery = useQuery({ queryKey: ["keys"], queryFn: getKeys });

  // Draft overrides layered over the saved settings (cleared once a save lands).
  const [draft, setDraft] = useState<SettingsPatch>({});
  // Translation style guidance: null = "in sync with saved", else an unsaved edit.
  const [promptDraft, setPromptDraft] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (patch: SettingsPatch) => updateSettings(patch),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      setDraft({});
    },
  });

  const savePrompt = useMutation({
    mutationFn: (patch: SettingsPatch) => updateSettings(patch),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      setPromptDraft(null);
    },
  });

  const reset = useMutation({
    mutationFn: () => resetSettings(),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      setDraft({});
    },
  });

  if (optionsQuery.isPending || settingsQuery.isPending) return <Shell><Loading /></Shell>;
  if (optionsQuery.isError || !optionsQuery.data || settingsQuery.isError || !settingsQuery.data)
    return (
      <Shell>
        <BackendError onRetry={() => { optionsQuery.refetch(); settingsQuery.refetch(); }} />
      </Shell>
    );

  const options = optionsQuery.data;
  const settings = settingsQuery.data;

  const translator = draft.defaultTranslator ?? settings.defaultTranslator;
  const tts = draft.defaultTts ?? settings.defaultTts;
  const dirty =
    (draft.defaultTranslator !== undefined && draft.defaultTranslator !== settings.defaultTranslator) ||
    (draft.defaultTts !== undefined && draft.defaultTts !== settings.defaultTts);

  const savedPrompt = settings.translation?.prompt ?? "";
  const promptValue = promptDraft ?? savedPrompt;
  const promptDirty = promptDraft !== null && promptDraft !== savedPrompt;

  return (
    <Shell>
      {/* Defaults -------------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle>{t("providers.title")}</CardTitle>
          <CardDescription>{t("providers.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Field id="defaultTranslator" label={t("providers.translator")}>
            <Select
              id="defaultTranslator"
              value={translator}
              onChange={(e) => setDraft((d) => ({ ...d, defaultTranslator: e.target.value }))}
            >
              {options.translators.map((tr) => (
                <option key={tr.id} value={tr.id}>
                  {tr.label} — {tr.description}
                </option>
              ))}
            </Select>
          </Field>

          <Field id="defaultTts" label={t("providers.tts")}>
            <Select
              id="defaultTts"
              value={tts}
              onChange={(e) => setDraft((d) => ({ ...d, defaultTts: e.target.value }))}
            >
              {options.ttsEngines.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.label} — {e.description}
                </option>
              ))}
            </Select>
          </Field>

          <div className="flex items-center gap-3 pt-1">
            <Button
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate({ defaultTranslator: translator, defaultTts: tts })}
            >
              {save.isPending ? <Loader2 className="animate-spin" /> : null}
              {t("providers.save")}
            </Button>
            {save.isSuccess && !dirty && (
              <span className="inline-flex items-center gap-1.5 text-sm text-success">
                <Check className="size-4" /> {t("providers.saved")}
              </span>
            )}
            {save.isError && (
              <span className="text-sm text-danger">{(save.error as Error).message}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* API providers (key + model + test) ------------------------------ */}
      <section>
        <div className="mb-3">
          <h2 className="type-h3">{t("keys.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("keys.desc")}</p>
        </div>
        <div className="space-y-4">
          {keysQuery.data?.keys.map((k) => {
            const opt = options.translators.find((tr) => tr.id === k.provider);
            return (
              <ProviderCard
                key={k.provider}
                providerId={k.provider}
                label={opt?.label ?? k.provider}
                defaultModel={opt?.defaultModel}
                status={k}
                savedModel={settings.providers?.[k.provider]?.model ?? null}
              />
            );
          })}
        </div>
      </section>

      {/* Translation style ----------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle>{t("translation.title")}</CardTitle>
          <CardDescription>{t("translation.desc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            rows={5}
            value={promptValue}
            placeholder={t("translation.placeholder")}
            onChange={(e) => setPromptDraft(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">{t("translation.hint")}</p>
          <div className="flex items-center gap-3">
            <Button
              disabled={!promptDirty || savePrompt.isPending}
              onClick={() =>
                savePrompt.mutate({ translation: { prompt: promptValue.trim() || null } })
              }
            >
              {savePrompt.isPending ? <Loader2 className="animate-spin" /> : null}
              {t("translation.save")}
            </Button>
            {savedPrompt && (
              <Button
                variant="outline"
                disabled={savePrompt.isPending}
                onClick={() => savePrompt.mutate({ translation: { prompt: null } })}
              >
                {t("translation.reset")}
              </Button>
            )}
            {savePrompt.isSuccess && !promptDirty && (
              <span className="inline-flex items-center gap-1.5 text-sm text-success">
                <Check className="size-4" /> {t("translation.saved")}
              </span>
            )}
            {savePrompt.isError && (
              <span className="text-sm text-danger">{(savePrompt.error as Error).message}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Appearance ------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <CardTitle>{t("appearance.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <Field id="theme" label={t("appearance.theme")}>
            <ThemeToggle />
          </Field>
          <Field id="language" label={t("appearance.language")}>
            <LanguageSwitcher />
          </Field>
        </CardContent>
      </Card>

      {/* Danger zone ----------------------------------------------------- */}
      <Card className="border-danger/30">
        <CardHeader>
          <CardTitle className="text-danger">{t("danger.title")}</CardTitle>
          <CardDescription>{t("danger.desc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            disabled={reset.isPending}
            onClick={() => {
              if (window.confirm(t("danger.confirm"))) reset.mutate();
            }}
          >
            {reset.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />}
            {t("danger.reset")}
          </Button>
        </CardContent>
      </Card>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("App.settings");
  return (
    <>
      <AppPageHeader title={t("title")} subtitle={t("subtitle")} />
      <div className="max-w-2xl space-y-6">{children}</div>
    </>
  );
}
