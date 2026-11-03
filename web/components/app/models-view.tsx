"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Check, Download, ExternalLink, Loader2, Mic, WifiOff } from "lucide-react";
import { getEngines, getOptions, installEngine, removeEngine } from "@/lib/api";
import type { EngineOption, InstallableEngine } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BackendError, Loading } from "./query-states";

const COMMERCIAL_BADGE = {
  yes: "success",
  credit: "success",
  no: "danger",
  unknown: "warning",
} as const;

function EngineCard({
  engine,
  offlineLabel,
  voiceCloneLabel,
}: {
  engine: EngineOption;
  offlineLabel: string;
  voiceCloneLabel: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{engine.label}</CardTitle>
        <CardDescription>{engine.description}</CardDescription>
      </CardHeader>
      {(engine.offline || engine.requiresVoiceSample) && (
        <CardContent className="flex gap-2">
          {engine.offline && (
            <Badge variant="success">
              <WifiOff /> {offlineLabel}
            </Badge>
          )}
          {engine.requiresVoiceSample && (
            <Badge variant="brand">
              <Mic /> {voiceCloneLabel}
            </Badge>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function InstallableEngineCard({
  engine,
  busy,
  onInstall,
  onRemove,
}: {
  engine: InstallableEngine;
  busy: boolean;
  onInstall: () => void;
  onRemove: () => void;
}) {
  const t = useTranslations("App.models");
  const installing = engine.install.status === "installing";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <CardTitle>{engine.label}</CardTitle>
            <CardDescription>{engine.description}</CardDescription>
          </div>
          {engine.installed && (
            <Badge variant="success">
              <Check /> {t("installed")}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant={COMMERCIAL_BADGE[engine.commercial]}>
            {engine.licence} · {t(`commercial.${engine.commercial}`)}
          </Badge>
          {engine.cloning && (
            <Badge variant="brand">
              <Mic /> {t("voiceClone")}
            </Badge>
          )}
          <Badge variant="outline" title={engine.languages.join(", ")}>
            {t("languages", { count: engine.languages.length })}
          </Badge>
          {!engine.installed && (
            <Badge variant="outline">
              <Download /> {t("download", { gb: engine.download_gb })}
            </Badge>
          )}
        </div>

        {engine.notice && <p className="text-sm text-muted-foreground">{engine.notice}</p>}

        {installing && engine.install.log.length > 0 && (
          <pre className="type-code max-h-48 overflow-auto rounded-sm border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
            {engine.install.log.slice(-12).join("\n")}
          </pre>
        )}
        {engine.install.status === "failed" && (
          <p className="text-sm text-danger">
            {t("installFailed")}: {engine.install.error}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3">
          {engine.installed ? (
            <Button variant="outline" disabled={busy} onClick={onRemove}>
              {t("remove")}
            </Button>
          ) : (
            <Button disabled={busy || installing} onClick={onInstall}>
              {installing ? <Loader2 className="animate-spin" /> : <Download />}
              {installing ? t("installing") : t("install")}
            </Button>
          )}
          <a
            href={engine.homepage}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("homepage")} <ExternalLink className="size-3.5" />
          </a>
        </div>
      </CardContent>
    </Card>
  );
}

/** Engines Voxa installs into environments of their own: install, watch, remove. */
function InstallableEngines() {
  const t = useTranslations("App.models");
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["engines"],
    queryFn: getEngines,
    // An install takes minutes; while one runs, its status and log are polled.
    refetchInterval: (q) =>
      q.state.data?.engines.some((e) => e.install.status === "installing") ? 1000 : false,
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["engines"] });
    // The job form offers an engine only once it is installed.
    queryClient.invalidateQueries({ queryKey: ["options"] });
  };
  const install = useMutation({ mutationFn: installEngine, onSettled: refresh });
  const remove = useMutation({ mutationFn: removeEngine, onSettled: refresh });

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data) return <BackendError onRetry={() => query.refetch()} />;

  const failure = install.error ?? remove.error;

  return (
    <section>
      <h2 className="type-label mb-2 text-muted-foreground">{t("installable")}</h2>
      {/* The folder is one long unbroken path, so it may wrap anywhere. */}
      <p className="mb-4 max-w-2xl text-sm text-muted-foreground [overflow-wrap:anywhere]">
        {t("installableHint", { dir: query.data.dir })}
      </p>
      {failure && <p className="mb-4 text-sm text-danger">{failure.message}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {query.data.engines.map((engine) => (
          <InstallableEngineCard
            key={engine.id}
            engine={engine}
            busy={install.isPending || remove.isPending}
            onInstall={() => {
              if (
                engine.commercial === "no" &&
                !window.confirm(t("ncConfirm", { label: engine.label }))
              )
                return;
              install.mutate(engine.id);
            }}
            onRemove={() => {
              if (window.confirm(t("removeConfirm", { label: engine.label })))
                remove.mutate(engine.id);
            }}
          />
        ))}
      </div>
    </section>
  );
}

export function ModelsView() {
  const t = useTranslations("App.models");
  const query = useQuery({ queryKey: ["options"], queryFn: getOptions });

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data)
    return <BackendError onRetry={() => query.refetch()} />;

  const options = query.data;

  return (
    <div className="space-y-12">
      <InstallableEngines />

      <section>
        <h2 className="type-label mb-4 text-muted-foreground">{t("translation")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {options.translators.map((e) => (
            <EngineCard
              key={e.id}
              engine={e}
              offlineLabel={t("offline")}
              voiceCloneLabel={t("voiceClone")}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="type-label mb-4 text-muted-foreground">{t("tts")}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {options.ttsEngines.map((e) => (
            <EngineCard
              key={e.id}
              engine={e}
              offlineLabel={t("offline")}
              voiceCloneLabel={t("voiceClone")}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="type-label mb-4 text-muted-foreground">{t("transcription")}</h2>
        <div className="flex flex-wrap gap-2">
          {options.whisperModels.map((m) => (
            <Badge key={m.id} variant="outline">
              Whisper {m.label}
            </Badge>
          ))}
        </div>
      </section>
    </div>
  );
}
