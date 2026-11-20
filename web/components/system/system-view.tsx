"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Globe,
  MinusCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { getDoctor } from "@/lib/api";
import type { DoctorCheck, DoctorReport } from "@/lib/types";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { BackendError, Loading } from "@/components/app/query-states";
import { cn } from "@/lib/utils";

const STATUS = {
  ok: { icon: CheckCircle2, tone: "text-success" },
  warn: { icon: AlertTriangle, tone: "text-warning" },
  fail: { icon: XCircle, tone: "text-danger" },
  off: { icon: MinusCircle, tone: "text-fg-subtle" },
} as const;

/** Where the console itself fixes what a check says: the place to go instead of a command. */
function placeFor(
  check: DoctorCheck,
): { href: string; key: "settings" | "speakers" | "engines" } | null {
  if (check.status === "ok") return null;
  if (check.section === "Translation" && /Settings/.test(check.fix))
    return { href: "/app/settings?section=translation", key: "settings" };
  if (check.name === "Diarization" && /HF_TOKEN/.test(check.fix))
    return { href: "/app/settings?section=speakers", key: "speakers" };
  if (/voxa engines install/.test(check.fix)) return { href: "/app/models", key: "engines" };
  return null;
}

function CheckRow({ check }: { check: DoctorCheck }) {
  const t = useTranslations("App.system");
  const ts = useTranslations("App.system.status");
  const { icon: Icon, tone } = STATUS[check.status];
  const place = placeFor(check);
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 px-3 py-2.5 sm:grid-cols-[1rem_11rem_minmax(0,1fr)]">
      <span role="img" aria-label={ts(check.status)} title={ts(check.status)} className="pt-0.5">
        <Icon aria-hidden className={cn("size-4", tone)} />
      </span>
      <span className="text-ui-body font-medium">{check.name}</span>
      <div className="col-start-2 min-w-0 space-y-1.5 sm:col-start-3">
        <p className="text-ui-body text-muted-foreground [overflow-wrap:anywhere]">
          {check.detail}
        </p>
        {check.fix &&
          check.status !== "ok" &&
          place?.key !== "settings" &&
          place?.key !== "speakers" && (
            <div className="flex items-start gap-1 rounded-sm border border-border bg-surface-2 py-1 pl-2.5 pr-1">
              <code className="min-w-0 flex-1 py-0.5 font-mono text-ui-mono text-foreground [overflow-wrap:anywhere]">
                {check.fix}
              </code>
              <CopyButton text={check.fix} label={t("copyFix")} />
            </div>
          )}
        {place && (
          <Link
            href={place.href}
            className="inline-flex items-center gap-1 text-ui-small text-primary hover:underline"
          >
            {t(`fixIn.${place.key}`)} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        )}
      </div>
    </li>
  );
}

function Summary({
  report,
  checking,
  online,
  onCheck,
}: {
  report: DoctorReport;
  checking: boolean;
  online: boolean;
  onCheck: (online: boolean) => void;
}) {
  const t = useTranslations("App.system");
  const failed = report.checks.filter((c) => c.status === "fail").length;
  const warned = report.checks.filter((c) => c.status === "warn").length;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-lg border border-border bg-surface-1 p-4">
      {report.ready ? (
        <CheckCircle2 className="size-6 shrink-0 text-success" aria-hidden />
      ) : (
        <XCircle className="size-6 shrink-0 text-danger" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-ui-section" aria-live="polite">
          {report.ready ? t("ready") : t("notReady", { count: failed })}
          {report.ready && warned ? (
            <span className="text-muted-foreground"> · {t("warnings", { count: warned })}</span>
          ) : null}
        </p>
        <p className="text-ui-small text-muted-foreground">
          {t("about", {
            version: report.version,
            python: report.python,
            os: report.os,
            install: t(`install.${report.install}`),
          })}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={() => onCheck(online)} loading={checking}>
          {!checking && <RefreshCw />} {t("again")}
        </Button>
        {!online && (
          <Button size="sm" variant="ghost" onClick={() => onCheck(true)} disabled={checking}>
            <Globe /> {t("online")}
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * What this install can do and how to fix what it can't: `voxa doctor`'s checks
 * (VOXA_DESIGN_PLAN.md §8.9), each fix in this install's own commands. Its internet checks
 * (Google, Edge, Hugging Face) are asked for; its deep ones, which load models, stay in the
 * command line.
 */
export function SystemView() {
  const t = useTranslations("App.system");
  const [online, setOnline] = useState(false);
  const query = useQuery({
    queryKey: ["doctor", online],
    queryFn: () => getDoctor(online),
    staleTime: 30_000,
  });
  // Shown while the next answer comes, so the page doesn't blank out on "Check again".
  const [last, setLast] = useState<DoctorReport | null>(null);
  const report = query.data ?? last;

  if (!report && query.isPending) return <Loading />;
  if (!report) return <BackendError onRetry={() => query.refetch()} />;

  const check = (withOnline: boolean) => {
    setLast(report);
    if (withOnline !== online) setOnline(withOnline);
    else void query.refetch();
  };

  return (
    <div className="max-w-4xl space-y-6">
      <Summary report={report} checking={query.isFetching} online={online} onCheck={check} />
      {report.sections.map((section) => {
        const rows = report.checks.filter((c) => c.section === section);
        if (!rows.length) return null;
        return (
          <section key={section} aria-labelledby={`system-${section}`} className="space-y-2">
            <h2 id={`system-${section}`} className="text-ui-label uppercase text-muted-foreground">
              {t.has(`sections.${section}`)
                ? t(`sections.${section}` as "sections.Required")
                : section}
            </h2>
            <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
              {rows.map((c) => (
                <CheckRow key={`${c.section}-${c.name}`} check={c} />
              ))}
            </ul>
          </section>
        );
      })}
      <p className="text-ui-small text-fg-subtle">{t("deepHint")}</p>
    </div>
  );
}
