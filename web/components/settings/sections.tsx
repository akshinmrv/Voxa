"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { Activity, ExternalLink, FolderOpen, Lock, RotateCcw } from "lucide-react";
import { getHealth, resetSettings } from "@/lib/api";
import { useDesktop } from "@/lib/desktop";
import { useUpdateStatus } from "@/lib/use-update";
import { SITE } from "@/lib/site";
import type { KeysStatus, VoxaOptions } from "@/lib/types";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { SegmentedControl } from "@/components/ui/segmented";
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
import { ThemeChoice } from "@/components/shell/theme-choice";
import { cn } from "@/lib/utils";
import type { Draft, Values } from "./draft";
import { KeyField } from "./key-field";
import { Group, Row } from "./row";

export type SectionProps = {
  values: Values;
  set: (patch: Draft) => void;
  options: VoxaOptions;
  keys: KeysStatus | undefined;
};

/** Each language by its own name, as a language list writes it. */
const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  az: "Azərbaycanca",
  tr: "Türkçe",
};

const NUMBER = "h-8 w-28 text-ui-body";
const SELECT = "h-8 text-ui-body";

export function GeneralSection({
  values,
  set,
  onLanguage,
}: SectionProps & { onLanguage: (locale: string) => void }) {
  const t = useTranslations("App.settings");
  const locale = useLocale();
  return (
    <Group>
      <Row id="language" label={t("appearance.language")}>
        <SegmentedControl
          aria-label={t("appearance.language")}
          value={locale}
          onValueChange={onLanguage}
          items={routing.locales.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] ?? l }))}
        />
      </Row>
      <Row id="theme" label={t("appearance.theme")}>
        <ThemeChoice />
      </Row>
      <Row
        id="autoDownload"
        htmlFor="autoDownload"
        label={t("advanced.autoDownloadLabel")}
        hint={t("advanced.autoDownloadHint")}
      >
        <Switch
          id="autoDownload"
          checked={values.autoDownload}
          onCheckedChange={(on) => set({ autoDownload: on })}
        />
      </Row>
      <Row
        id="checkUpdates"
        htmlFor="checkUpdates"
        label={t("advanced.checkUpdatesLabel")}
        hint={t("advanced.checkUpdatesHint")}
      >
        <Switch
          id="checkUpdates"
          checked={values.checkUpdates}
          onCheckedChange={(on) => set({ checkUpdates: on })}
        />
      </Row>
    </Group>
  );
}

export function TranslationSection({ values, set, options, keys }: SectionProps) {
  const t = useTranslations("App.settings");
  return (
    <>
      <Group>
        <Row
          id="defaultTranslator"
          htmlFor="defaultTranslator"
          label={t("providers.translator")}
          hint={t("providers.desc")}
        >
          <Select
            id="defaultTranslator"
            className={SELECT}
            value={values.defaultTranslator}
            onChange={(e) => set({ defaultTranslator: e.target.value })}
          >
            {options.translators.map((tr) => (
              <option key={tr.id} value={tr.id}>
                {tr.label}
              </option>
            ))}
          </Select>
        </Row>
        <Row
          id="fallback"
          htmlFor="fallback"
          label={t("advanced.fallbackLabel")}
          hint={t("advanced.fallbackHint")}
        >
          <Select
            id="fallback"
            className={SELECT}
            value={values.fallback}
            onChange={(e) => set({ fallback: e.target.value })}
          >
            <option value="">{t("advanced.fallbackNone")}</option>
            {options.translators.map((tr) => (
              <option key={tr.id} value={tr.id}>
                {tr.label}
              </option>
            ))}
          </Select>
        </Row>
      </Group>

      <Group title={t("keys.title")}>
        <p className="px-4 py-3 text-ui-small text-muted-foreground">{t("keys.desc")}</p>
        {keys?.keys.map((k) => {
          const option = options.translators.find((tr) => tr.id === k.provider);
          const label = option?.label ?? k.provider;
          return (
            <Row key={k.provider} id={`key-${k.provider}`} wide>
              <KeyField provider={k.provider} label={label} status={k}>
                {() => (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <label
                      htmlFor={`model-${k.provider}`}
                      className="text-ui-small text-muted-foreground"
                    >
                      {t("keys.modelLabel")}
                    </label>
                    <Input
                      id={`model-${k.provider}`}
                      value={values.models[k.provider] ?? ""}
                      placeholder={option?.defaultModel}
                      onChange={(e) =>
                        set({ models: { ...values.models, [k.provider]: e.target.value } })
                      }
                      className="h-8 max-w-xs font-mono text-ui-mono"
                    />
                  </div>
                )}
              </KeyField>
            </Row>
          );
        })}
      </Group>

      <Group>
        <Row
          id="prompt"
          htmlFor="prompt"
          label={t("translation.title")}
          hint={
            <>
              <p>{t("translation.desc")}</p>
              <p className="mt-1">{t("translation.hint")}</p>
            </>
          }
        >
          <Textarea
            id="prompt"
            rows={5}
            value={values.prompt}
            placeholder={t("translation.placeholder")}
            onChange={(e) => set({ prompt: e.target.value })}
          />
        </Row>
      </Group>
    </>
  );
}

export function SpeechSection({ values, set, options }: SectionProps) {
  const t = useTranslations("App.settings");
  const togglePreset = (id: string) =>
    set({
      presets: values.presets.includes(id)
        ? values.presets.filter((p) => p !== id)
        : [...values.presets, id],
    });
  return (
    <>
      <Group>
        <Row id="defaultTts" htmlFor="defaultTts" label={t("providers.tts")}>
          <Select
            id="defaultTts"
            className={SELECT}
            value={values.defaultTts}
            onChange={(e) => set({ defaultTts: e.target.value })}
          >
            {options.ttsEngines.map((e) => (
              <option
                key={e.id}
                value={e.id}
                disabled={e.available === false && e.id !== values.defaultTts}
              >
                {e.label}
                {e.available === false ? ` — ${t("speech.notInstalled")}` : ""}
              </option>
            ))}
          </Select>
        </Row>
        <Row
          id="qualityGate"
          htmlFor="qualityGate"
          label={t("advanced.qualityGateLabel")}
          hint={t("advanced.qualityGateHint")}
        >
          <Switch
            id="qualityGate"
            checked={values.qualityGate}
            onCheckedChange={(on) => set({ qualityGate: on })}
          />
        </Row>
      </Group>

      <Group title={t("speech.title")}>
        <p className="px-4 py-3 text-ui-small text-muted-foreground">{t("speech.desc")}</p>
        <Row id="presets" label={t("speech.presetsLabel")}>
          <div className="flex flex-wrap gap-1.5">
            {options.speechPresets.map((p) => {
              const on = values.presets.includes(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => togglePreset(p.id)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-ui-small font-medium transition-colors duration-(--dur-1)",
                    on
                      ? "border-primary/40 bg-primary/15 text-primary"
                      : "border-border bg-surface-1 text-muted-foreground hover:border-primary/40",
                  )}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </Row>
        <Row id="instructions" htmlFor="instructions" label={t("speech.textLabel")}>
          <Textarea
            id="instructions"
            rows={3}
            value={values.instructions}
            placeholder={t("speech.placeholder")}
            onChange={(e) => set({ instructions: e.target.value })}
          />
        </Row>
        <div className="flex gap-3 px-4 py-3">
          <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <p className="text-ui-small text-muted-foreground">{t("speech.guard")}</p>
        </div>
      </Group>
    </>
  );
}

export function SpeakersSection({ options, keys }: SectionProps) {
  const t = useTranslations("App.settings.speakers");
  const hf = keys?.hf;
  return (
    <>
      {options.diarizeAvailable === false && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3">
          <p className="min-w-0 flex-1 text-ui-body">{t("notInstalled")}</p>
          <Button asChild size="sm" variant="secondary">
            <Link href="/app/system">
              <Activity /> {t("openSystem")}
            </Link>
          </Button>
        </div>
      )}
      <Group>
        <Row id="hfToken" label={t("token")} hint={t("desc")} wide>
          <div className="space-y-4">
            <ol className="list-decimal space-y-2 pl-5 text-ui-body text-muted-foreground marker:text-fg-subtle">
              <li>
                {t("step1")}
                <span className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                  {(hf?.models ?? []).map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-mono text-ui-mono text-primary hover:underline"
                    >
                      {url.replace("https://huggingface.co/", "")}
                      <ExternalLink className="size-3" aria-hidden />
                    </a>
                  ))}
                </span>
              </li>
              <li>
                {t("step2")}{" "}
                <a
                  href="https://huggingface.co/settings/tokens"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  huggingface.co/settings/tokens <ExternalLink className="size-3" aria-hidden />
                </a>
              </li>
              <li>{t("step3")}</li>
            </ol>
            {hf && (
              <KeyField provider="hf" label={hf.envKey} status={hf} placeholder={t("paste")} />
            )}
          </div>
        </Row>
      </Group>
    </>
  );
}

export function PerformanceSection({ values, set, options }: SectionProps) {
  const t = useTranslations("App.settings.advanced");
  return (
    <Group>
      <Row
        id="device"
        htmlFor="device"
        label={t("deviceLabel")}
        hint={values.device === "mps" ? t("deviceMpsHint") : t("deviceHint")}
      >
        <Select
          id="device"
          className={SELECT}
          value={values.device}
          onChange={(e) => set({ device: e.target.value as Values["device"] })}
        >
          <option value="auto">{t("deviceAuto")}</option>
          <option value="cpu">{t("deviceCpu")}</option>
          <option value="cuda" disabled={!options.gpu?.cuda && values.device !== "cuda"}>
            {t("deviceCuda")}
            {options.gpu?.cuda ? "" : ` — ${t("deviceMissing")}`}
          </option>
          <option value="mps" disabled={!options.gpu?.mps && values.device !== "mps"}>
            {t("deviceMps")}
            {options.gpu?.mps ? "" : ` — ${t("deviceMissing")}`}
          </option>
        </Select>
      </Row>
      <Row
        id="maxConcurrentJobs"
        htmlFor="maxConcurrentJobs"
        label={t("concurrentLabel")}
        hint={t("concurrentHint")}
      >
        <Input
          id="maxConcurrentJobs"
          type="number"
          min={1}
          max={4}
          step={1}
          placeholder="1"
          className={NUMBER}
          value={values.maxConcurrentJobs}
          onChange={(e) => set({ maxConcurrentJobs: e.target.value })}
        />
      </Row>
      <Row id="ttsWorkers" htmlFor="ttsWorkers" label={t("workersLabel")} hint={t("workersHint")}>
        <Input
          id="ttsWorkers"
          type="number"
          min={1}
          max={16}
          step={1}
          placeholder="4"
          className={NUMBER}
          value={values.ttsWorkers}
          onChange={(e) => set({ ttsWorkers: e.target.value })}
        />
      </Row>
      <Row id="speechRate" htmlFor="speechRate" label={t("rateLabel")} hint={t("rateHint")}>
        <Input
          id="speechRate"
          type="number"
          min={8}
          max={30}
          step={0.5}
          placeholder="15"
          className={NUMBER}
          value={values.speechRate}
          onChange={(e) => set({ speechRate: e.target.value })}
        />
      </Row>
    </Group>
  );
}

export function AboutSection() {
  const t = useTranslations("App.settings.about");
  const desktop = useDesktop();
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });
  const update = useUpdateStatus().data;
  const info = useQuery({
    queryKey: ["appInfo"],
    queryFn: () => desktop!.app_info(),
    enabled: !!desktop,
    staleTime: Infinity,
  });
  const version = health.data?.version ?? update?.current ?? "";
  const status = !update
    ? null
    : update.disabled
      ? t("updateOff")
      : update.newer
        ? t("newer", { latest: update.latest ?? "" })
        : update.latest === update.current
          ? t("newest")
          : update.latest
            ? t("pypiNewest", { latest: update.latest })
            : t("updateUnknown");
  const link = "inline-flex items-center gap-1 text-ui-body text-primary hover:underline";
  return (
    <Group>
      <Row id="version" label={t("version")}>
        <p className="text-ui-body">
          <span className="font-mono text-ui-mono">Voxa {version}</span>
          {status && <span className="text-muted-foreground"> · {status}</span>}
        </p>
        {update?.newer && update.notes && (
          <a
            className={cn(link, "mt-1")}
            href={update.notes}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("notes")} <ExternalLink className="size-3.5" aria-hidden />
          </a>
        )}
      </Row>
      {desktop && info.data && (
        <Row id="window" label={t("window")}>
          <p className="font-mono text-ui-mono text-muted-foreground [overflow-wrap:anywhere]">
            {[
              info.data.shell ? `pywebview ${info.data.shell}` : null,
              info.data.renderer,
              info.data.os,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </Row>
      )}
      <Row id="systemCheck" label={t("system")} hint={t("systemHint")}>
        <Button asChild size="sm" variant="secondary">
          <Link href="/app/system">
            <Activity /> {t("openSystem")}
          </Link>
        </Button>
      </Row>
      {desktop && (
        <Row id="logs" label={t("logs")} hint={t("logsHint")}>
          <Button size="sm" variant="secondary" onClick={() => desktop.open_logs()}>
            <FolderOpen /> {t("openLogs")}
          </Button>
        </Row>
      )}
      <Row id="links" label={t("links")}>
        <div className="flex flex-wrap gap-x-5 gap-y-1.5">
          {[
            { href: `${SITE.repo}#readme`, label: t("docs") },
            { href: SITE.url, label: t("website") },
            { href: SITE.repo, label: "GitHub" },
            { href: `${SITE.repo}/blob/main/NOTICE.md`, label: t("licences") },
          ].map((l) => (
            <a
              key={l.href}
              className={link}
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
            >
              {l.label} <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ))}
        </div>
      </Row>
    </Group>
  );
}

export function ResetSection({ onReset }: { onReset: () => void }) {
  const t = useTranslations("App.settings.danger");
  const common = useTranslations("Common");
  const qc = useQueryClient();
  const [ask, setAsk] = useState(false);
  const reset = useMutation({
    mutationFn: resetSettings,
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      void qc.invalidateQueries({ queryKey: ["update"] });
      setAsk(false);
      onReset();
    },
  });
  return (
    <>
      <Group>
        <Row id="reset" label={t("reset")} hint={t("desc")}>
          <Button size="sm" variant="destructive" onClick={() => setAsk(true)}>
            <RotateCcw /> {t("reset")}
          </Button>
        </Row>
      </Group>
      <AlertDialog open={ask} onOpenChange={setAsk}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("confirm")}</AlertDialogTitle>
            <AlertDialogDescription>{t("resetBody")}</AlertDialogDescription>
          </AlertDialogHeader>
          {reset.isError && (
            <p className="text-ui-small text-danger">{(reset.error as Error).message}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive
              disabled={reset.isPending}
              onClick={(e) => {
                e.preventDefault();
                reset.mutate();
              }}
            >
              {t("reset")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
