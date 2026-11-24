"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Copyright,
  Download,
  ExternalLink,
  HelpCircle,
  Info,
  Mic,
  MinusCircle,
  WifiOff,
  XCircle,
} from "lucide-react";
import { getDoctor, getEngines, getOptions, installEngine, removeEngine } from "@/lib/api";
import type { DoctorCheck, EngineOption, InstallableEngine } from "@/lib/types";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
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
import { BackendError, Loading } from "@/components/app/query-states";
import { cn } from "@/lib/utils";

/** What a licence allows commercially, by icon and word: never by colour alone. */
const COMMERCIAL = {
  yes: { icon: CheckCircle2, tone: "text-success" },
  credit: { icon: Copyright, tone: "text-success" },
  no: { icon: Ban, tone: "text-danger" },
  unknown: { icon: HelpCircle, tone: "text-warning" },
} as const;

const STATUS = {
  ok: { icon: CheckCircle2, tone: "text-success" },
  warn: { icon: AlertTriangle, tone: "text-warning" },
  fail: { icon: XCircle, tone: "text-danger" },
  off: { icon: MinusCircle, tone: "text-fg-subtle" },
} as const;

/** The doctor's names for the engines built in, by their ids. */
const DOCTOR_NAME: Record<string, Record<string, string>> = {
  Translation: {
    google: "Google",
    ollama: "Ollama",
    openai: "OpenAI",
    anthropic: "Anthropic",
    openrouter: "OpenRouter",
  },
  Speech: { edge: "Edge", piper: "Piper", openai: "OpenAI", xtts: "XTTS" },
};

function InstallableCard({
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
  const { icon: Licence, tone } = COMMERCIAL[engine.commercial];
  const log = useRef<HTMLPreElement>(null);
  const lines = engine.install.log.slice(-200);

  // The newest line of the log in view, as it comes.
  useEffect(() => {
    log.current?.scrollTo(0, log.current.scrollHeight);
  }, [lines.length]);

  return (
    <article className="space-y-4 rounded-lg border border-border bg-surface-1 p-4">
      <header className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-ui-section">{engine.label}</h3>
          <p className="mt-1 text-ui-body text-muted-foreground">{engine.description}</p>
        </div>
        {engine.installed ? (
          <span className="inline-flex items-center gap-2">
            <Badge variant="success">
              <CheckCircle2 /> {t("installed")}
            </Badge>
            <Button size="sm" variant="ghost" disabled={busy} onClick={onRemove}>
              {t("remove")}
            </Button>
          </span>
        ) : (
          <Button size="sm" disabled={busy || installing} loading={installing} onClick={onInstall}>
            {!installing && <Download />}
            {installing ? t("installing") : t("installSize", { gb: engine.download_gb })}
          </Button>
        )}
      </header>

      {/* The licence is the line that matters most before a download of gigabytes. */}
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-sm border border-border bg-surface-2 px-3 py-2 text-ui-body">
        <Licence className={cn("size-4 shrink-0", tone)} aria-hidden />
        <span>
          {t("licence")}: <span className="font-medium">{engine.licence}</span>
        </span>
        <span className="text-muted-foreground">·</span>
        <span className={tone}>{t(`commercial.${engine.commercial}`)}</span>
        <a
          href={engine.homepage}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto inline-flex items-center gap-1 text-ui-small text-muted-foreground transition-colors hover:text-foreground"
        >
          {t("homepage")} <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </p>

      <div className="flex flex-wrap gap-2">
        {engine.cloning && (
          <Badge variant="brand">
            <Mic /> {t("voiceClone")}
          </Badge>
        )}
        <Badge variant="outline" title={engine.languages.join(", ")}>
          {engine.languages.length
            ? t("languages", { count: engine.languages.length })
            : t("anyLanguage")}
        </Badge>
      </div>

      {engine.notice && (
        <p className="flex gap-2 text-ui-small text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          {engine.notice}
        </p>
      )}

      {/* The log stays after a failure: its last lines are what says why. */}
      {(installing || engine.install.status === "failed") && lines.length > 0 && (
        <pre
          ref={log}
          aria-label={t("log")}
          aria-live="polite"
          className="max-h-48 overflow-auto rounded-sm border border-border bg-surface-2 p-3 font-mono text-ui-mono text-muted-foreground"
        >
          {lines.join("\n")}
        </pre>
      )}
      {engine.install.status === "failed" && (
        <p className="text-ui-small text-danger [overflow-wrap:anywhere]">
          {t("installFailed")}: {engine.install.error}
        </p>
      )}
    </article>
  );
}

/** Engines Voxa installs into environments of their own: install, watch, remove. */
function Installable() {
  const t = useTranslations("App.models");
  const common = useTranslations("Common");
  const queryClient = useQueryClient();
  const [ask, setAsk] = useState<{ kind: "install" | "remove"; engine: InstallableEngine } | null>(
    null,
  );
  const query = useQuery({
    queryKey: ["engines"],
    queryFn: getEngines,
    // An install takes minutes; while one runs, its status and log are asked for every second.
    refetchInterval: (q) =>
      q.state.data?.engines.some((e) => e.install.status === "installing") ? 1000 : false,
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["engines"] });
    // The Studio offers an engine only once it is installed; the doctor says so too.
    queryClient.invalidateQueries({ queryKey: ["options"] });
    queryClient.invalidateQueries({ queryKey: ["doctor"] });
  };
  const install = useMutation({ mutationFn: installEngine, onSettled: refresh });
  const remove = useMutation({ mutationFn: removeEngine, onSettled: refresh });

  if (query.isPending) return <Loading />;
  if (query.isError || !query.data) return <BackendError onRetry={() => query.refetch()} />;

  const failure = install.error ?? remove.error;
  return (
    <section aria-labelledby="engines-installable" className="space-y-3">
      <h2 id="engines-installable" className="text-ui-label uppercase text-muted-foreground">
        {t("installable")}
      </h2>
      {/* The folder is one long unbroken path, so it may wrap anywhere. */}
      <p className="max-w-3xl text-ui-small text-muted-foreground [overflow-wrap:anywhere]">
        {t("installableHint", { dir: query.data.dir })}
      </p>
      {failure && <p className="text-ui-small text-danger">{failure.message}</p>}
      <div className="grid gap-4 xl:grid-cols-2">
        {query.data.engines.map((engine) => (
          <InstallableCard
            key={engine.id}
            engine={engine}
            busy={install.isPending || remove.isPending}
            onInstall={() =>
              engine.commercial === "no"
                ? setAsk({ kind: "install", engine })
                : install.mutate(engine.id)
            }
            onRemove={() => setAsk({ kind: "remove", engine })}
          />
        ))}
      </div>

      <AlertDialog open={ask !== null} onOpenChange={(open) => !open && setAsk(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {ask?.kind === "remove"
                ? t("removeTitle", { label: ask.engine.label })
                : t("ncTitle", { label: ask?.engine.label ?? "" })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {ask?.kind === "remove"
                ? t("removeConfirm", { label: ask.engine.label })
                : t("ncConfirm", { label: ask?.engine.label ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive={ask?.kind === "remove"}
              onClick={() => {
                if (!ask) return;
                if (ask.kind === "remove") remove.mutate(ask.engine.id);
                else install.mutate(ask.engine.id);
              }}
            >
              {ask?.kind === "remove" ? t("remove") : t("install")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

/** One engine built into Voxa, and what `voxa doctor` says about it here. */
function BuiltInRow({ engine, check }: { engine: EngineOption; check?: DoctorCheck }) {
  const t = useTranslations("App.models");
  const ts = useTranslations("App.system.status");
  const state = check ? STATUS[check.status] : null;
  const keyed = check?.status === "off" && /Settings/.test(check.fix);
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-3 gap-y-1 px-3 py-3 sm:grid-cols-[1rem_10rem_minmax(0,1fr)]">
      {state && check ? (
        <span role="img" aria-label={ts(check.status)} title={ts(check.status)} className="pt-0.5">
          <state.icon aria-hidden className={cn("size-4", state.tone)} />
        </span>
      ) : (
        <span />
      )}
      <span className="text-ui-body font-medium">{engine.label}</span>
      <div className="col-start-2 min-w-0 space-y-1.5 sm:col-start-3">
        <p className="text-ui-body text-muted-foreground">{engine.description}</p>
        {(engine.offline || engine.requiresVoiceSample) && (
          <div className="flex flex-wrap gap-2">
            {engine.offline && (
              <Badge variant="neutral">
                <WifiOff /> {t("offline")}
              </Badge>
            )}
            {engine.requiresVoiceSample && (
              <Badge variant="brand">
                <Mic /> {t("voiceClone")}
              </Badge>
            )}
          </div>
        )}
        {check && check.status !== "ok" && (
          <p className="text-ui-small text-muted-foreground [overflow-wrap:anywhere]">
            {check.detail}
          </p>
        )}
        {check && check.status !== "ok" && check.fix && !keyed && (
          <div className="flex items-start gap-1 rounded-sm border border-border bg-surface-2 py-1 pl-2.5 pr-1">
            <code className="min-w-0 flex-1 py-0.5 font-mono text-ui-mono [overflow-wrap:anywhere]">
              {check.fix}
            </code>
            <CopyButton text={check.fix} />
          </div>
        )}
        {keyed && (
          <Link
            href="/app/settings?section=translation"
            className="inline-flex text-ui-small text-primary hover:underline"
          >
            {t("addKey")}
          </Link>
        )}
      </div>
    </li>
  );
}

function BuiltInGroup({
  title,
  section,
  engines,
  checks,
}: {
  title: string;
  section: "Translation" | "Speech";
  engines: EngineOption[];
  checks: DoctorCheck[] | undefined;
}) {
  const find = (id: string) =>
    checks?.find((c) => c.section === section && c.name === DOCTOR_NAME[section][id]);
  return (
    <div className="space-y-2">
      <h3 className="text-ui-label uppercase text-muted-foreground">{title}</h3>
      <ul className="divide-y divide-border rounded-lg border border-border bg-surface-1">
        {engines.map((e) => (
          <BuiltInRow key={e.id} engine={e} check={find(e.id)} />
        ))}
      </ul>
    </div>
  );
}

/**
 * Engines (VOXA_DESIGN_PLAN.md §8.7): the ones Voxa installs on request first, each with what
 * its licence allows; then the ones built in, with what `voxa doctor` says about each here.
 */
export function EnginesView() {
  const t = useTranslations("App.models");
  const options = useQuery({ queryKey: ["options"], queryFn: getOptions });
  // The same list Installable asks for: its engines aren't built in, installed or not.
  const installable = useQuery({ queryKey: ["engines"], queryFn: getEngines });
  const doctor = useQuery({
    queryKey: ["doctor", false],
    queryFn: () => getDoctor(false),
    staleTime: 30_000,
  });

  if (options.isPending) return <Loading />;
  if (options.isError || !options.data) return <BackendError onRetry={() => options.refetch()} />;

  const checks = doctor.data?.checks;
  const faster = checks?.find((c) => c.name === "faster-whisper");
  const separate = new Set(installable.data?.engines.map((e) => e.id) ?? []);
  const builtInTts = options.data.ttsEngines.filter(
    (e) => !separate.has(e.id) && (installable.data || e.available !== false),
  );

  return (
    <div className="max-w-5xl space-y-10">
      <Installable />

      <section aria-labelledby="engines-builtin" className="space-y-5">
        <h2 id="engines-builtin" className="text-ui-label uppercase text-muted-foreground">
          {t("builtIn")}
        </h2>
        <div className="space-y-2">
          <h3 className="text-ui-label uppercase text-muted-foreground">{t("transcription")}</h3>
          <div className="space-y-2 rounded-lg border border-border bg-surface-1 p-3">
            <p className="text-ui-body text-muted-foreground">{t("whisper")}</p>
            <div className="flex flex-wrap gap-1.5">
              {options.data.whisperModels.map((m) => (
                <Badge key={m.id} variant="outline" className="font-mono">
                  {m.label}
                </Badge>
              ))}
            </div>
            {faster && (
              <p className="text-ui-small text-muted-foreground">
                faster-whisper: {faster.detail}
                {faster.status !== "ok" && faster.fix ? (
                  <span className="mt-1 flex items-start gap-1 rounded-sm border border-border bg-surface-2 py-1 pl-2.5 pr-1">
                    <code className="min-w-0 flex-1 py-0.5 font-mono text-ui-mono text-foreground [overflow-wrap:anywhere]">
                      {faster.fix}
                    </code>
                    <CopyButton text={faster.fix} />
                  </span>
                ) : null}
              </p>
            )}
          </div>
        </div>
        <BuiltInGroup
          title={t("translation")}
          section="Translation"
          engines={options.data.translators}
          checks={checks}
        />
        <BuiltInGroup title={t("tts")} section="Speech" engines={builtInTts} checks={checks} />
      </section>
    </div>
  );
}
