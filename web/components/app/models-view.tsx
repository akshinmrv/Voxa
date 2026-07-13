"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { WifiOff, Mic } from "lucide-react";
import { getOptions } from "@/lib/api";
import type { EngineOption } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BackendError, Loading } from "./query-states";

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

export function ModelsView() {
  const t = useTranslations("App.models");
  const query = useQuery({ queryKey: ["options"], queryFn: getOptions });

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data)
    return <BackendError onRetry={() => query.refetch()} />;

  const options = query.data;

  return (
    <div className="space-y-12">
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
