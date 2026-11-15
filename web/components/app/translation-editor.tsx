"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { AudioLines, Check, Loader2 } from "lucide-react";
import { getTranslation, putTranslation, voiceJob } from "@/lib/api";
import type { JobStatus, TranslationLine } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Loading } from "./query-states";

/** As the server keeps a line: its words with the spacing evened out. */
const tidy = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

function clock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

/**
 * A job's translated lines, each under the line it came from, to change before they are voiced
 * (a job waiting for review) or to change and voice again (a finished one: only the changed
 * lines are voiced again). Only the words can change; each line keeps its time.
 */
export function TranslationEditor({
  jobId,
  status,
  onVoice,
}: {
  jobId: string;
  status: JobStatus;
  /** Called once the job is queued to be voiced. */
  onVoice: () => void;
}) {
  const t = useTranslations("App.review");
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["translation", jobId],
    queryFn: () => getTranslation(jobId),
  });
  // Only the lines typed into are held here; the rest show what the server keeps.
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  const lines: TranslationLine[] = query.data?.lines ?? [];
  const texts = lines.map((line, i) => drafts[i] ?? line.text);
  const unsaved = lines.filter((line, i) => drafts[i] !== undefined && tidy(drafts[i]) !== line.text)
    .length;
  const nothingToSay = texts.every((text) => !tidy(text));

  const save = useMutation({
    mutationFn: () => putTranslation(jobId, texts),
    onSuccess: (data) => {
      qc.setQueryData(["translation", jobId], data);
      setDrafts({});
    },
  });
  const voice = useMutation({
    mutationFn: async () => {
      if (unsaved) qc.setQueryData(["translation", jobId], await putTranslation(jobId, texts));
      return voiceJob(jobId);
    },
    onSuccess: (summary) => {
      setDrafts({});
      qc.setQueryData(["job", jobId], summary);
      onVoice();
    },
  });

  if (query.isPending) return <Loading />;
  if (query.isError) {
    return <p className="text-sm text-danger">{(query.error as Error).message}</p>;
  }
  const editable = query.data.editable && !voice.isPending;
  const reviewing = status === "review";
  const error = (save.error ?? voice.error) as Error | null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{reviewing ? t("title") : t("editTitle")}</CardTitle>
        <CardDescription>{reviewing ? t("desc") : t("editDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="divide-y divide-border">
          {lines.map((line, i) => {
            const text = texts[i];
            const length = tidy(text).length;
            const long = length > line.maxChars;
            return (
              <li key={i} className="grid gap-2 py-3 first:pt-0 sm:grid-cols-[6.5rem_1fr]">
                <div className="flex flex-wrap items-start gap-2 pt-0.5 text-xs text-muted-foreground sm:flex-col">
                  <span className="tabular-nums">
                    {clock(line.start)}–{clock(line.end)}
                  </span>
                  {line.speaker && <Badge variant="neutral">{line.speaker}</Badge>}
                </div>
                <div className="min-w-0 space-y-1.5">
                  {line.source && (
                    <p className="text-sm text-muted-foreground">{line.source}</p>
                  )}
                  <Textarea
                    rows={2}
                    value={text}
                    disabled={!editable}
                    aria-label={t("lineLabel", { n: i + 1 })}
                    onChange={(e) => setDrafts((d) => ({ ...d, [i]: e.target.value }))}
                  />
                  <p
                    className={cn(
                      "text-xs tabular-nums",
                      long ? "text-warning" : "text-fg-subtle",
                    )}
                  >
                    {length === 0
                      ? t("silent")
                      : long
                        ? t("long", { length, max: line.maxChars })
                        : t("fits", { length, max: line.maxChars })}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
          <Button
            onClick={() => voice.mutate()}
            disabled={!editable || nothingToSay || save.isPending}
          >
            {voice.isPending ? <Loader2 className="animate-spin" /> : <AudioLines />}
            {reviewing ? t("voice") : t("voiceAgain")}
          </Button>
          <Button
            variant="secondary"
            onClick={() => save.mutate()}
            disabled={!editable || !unsaved || nothingToSay || save.isPending}
          >
            {save.isPending && <Loader2 className="animate-spin" />}
            {t("save")}
          </Button>
          {unsaved > 0 ? (
            <span className="text-sm text-muted-foreground">{t("unsaved", { count: unsaved })}</span>
          ) : (
            save.isSuccess && (
              <span className="inline-flex items-center gap-1.5 text-sm text-success">
                <Check className="size-4" /> {t("saved")}
              </span>
            )
          )}
          {nothingToSay && <span className="text-sm text-warning">{t("nothingToSay")}</span>}
          {error && <span className="text-sm text-danger">{error.message}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
