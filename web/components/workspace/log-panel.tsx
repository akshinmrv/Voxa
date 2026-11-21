"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown, Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

// "2026-11-17 02:10:39,106 - INFO - [3/7] Transcribing…": the time and the level apart.
// The pipe loses a line's trailing space, so an empty message ends at "INFO -".
const LINE = /^(?:\d{4}-\d\d-\d\d )?(\d\d:\d\d:\d\d)(?:,\d+)? - ([A-Z]+) -(?: (.*))?$/;

type Kind = "error" | "warning" | "step" | "info";

function parse(raw: string): { time: string | null; kind: Kind; text: string } {
  const m = LINE.exec(raw);
  const time = m ? m[1] : null;
  const level = m ? m[2] : "";
  const text = m ? (m[3] ?? "") : raw;
  const kind: Kind =
    level === "ERROR" || level === "CRITICAL" || /^\s*❌/.test(text)
      ? "error"
      : level === "WARNING" || /^\s*⚠/.test(text)
        ? "warning"
        : /\[\d\/7\]/.test(text)
          ? "step"
          : "info";
  return { time, kind, text };
}

const KIND: Record<Kind, string> = {
  error: "text-danger",
  warning: "text-warning",
  step: "text-foreground",
  info: "text-muted-foreground",
};

/**
 * A dub's log as it comes: each line's time apart from what it says, problems in colour (and
 * findable on their own), following the end unless you've scrolled up to read, the whole of
 * it copied with one click.
 */
export function LogPanel({
  lines,
  live,
  emptyText,
  className,
}: {
  lines: string[];
  /** Still coming: an empty log says so rather than "nothing". */
  live: boolean;
  emptyText: string;
  className?: string;
}) {
  const t = useTranslations("App.job");
  const common = useTranslations("Common");
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  const [problems, setProblems] = useState(false);
  const [copied, setCopied] = useState(false);
  // A log line with nothing to say (voxa's blank separators) is left out.
  const parsed = lines.map(parse).filter((l) => l.text.trim() !== "");
  const shown = problems
    ? parsed.filter((l) => l.kind === "error" || l.kind === "warning")
    : parsed;

  // Stay at the end as lines come in, while the reader is there.
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines.length, follow, problems]);

  function onScroll() {
    const el = box.current;
    if (!el) return;
    const atEnd = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (atEnd !== follow) setFollow(atEnd);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* no clipboard: nothing to say */
    }
  }

  return (
    <div className={cn("overflow-hidden rounded-lg border border-border bg-surface-1", className)}>
      <div className="flex items-center gap-3 border-b border-border px-3 py-2">
        <span className="text-ui-label uppercase text-muted-foreground">{t("logs")}</span>
        <span className="font-mono text-ui-mono tabular text-fg-subtle">{lines.length}</span>
        <span className="flex-1" />
        <label className="flex items-center gap-2 text-ui-small text-muted-foreground">
          <Switch checked={problems} onCheckedChange={setProblems} />
          {t("onlyProblems")}
        </label>
        <Button
          variant="ghost"
          size="xs"
          onClick={copy}
          disabled={!lines.length}
          aria-live="polite"
        >
          {copied ? <Check /> : <Copy />}
          {copied ? common("copied") : common("copy")}
        </Button>
      </div>
      <div className="relative">
        <div
          ref={box}
          onScroll={onScroll}
          role="log"
          aria-live="off"
          // Focusable, so the log scrolls by keyboard too.
          tabIndex={0}
          aria-label={t("tabLog")}
          className="max-h-80 overflow-y-auto px-3 py-2 font-mono text-ui-mono"
        >
          {shown.length ? (
            shown.map((line, i) => (
              <div key={i} className="flex gap-3 whitespace-pre-wrap break-words py-px">
                <span className="w-16 shrink-0 tabular text-fg-subtle">{line.time ?? ""}</span>
                <span className={cn("min-w-0", KIND[line.kind])}>{line.text}</span>
              </div>
            ))
          ) : (
            <p className="py-2 text-muted-foreground">
              {problems ? t("noProblems") : live ? emptyText : "—"}
            </p>
          )}
        </div>
        {!follow && (
          <Button
            size="xs"
            variant="secondary"
            className="absolute bottom-2 right-3 shadow-overlay"
            onClick={() => setFollow(true)}
          >
            <ArrowDown /> {t("newLines")}
          </Button>
        )}
      </div>
    </div>
  );
}
