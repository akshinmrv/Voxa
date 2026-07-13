"use client";

import { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Terminal / code block — real monospace command, copy button (DESIGN_SYSTEM.md §8.5).
 * `label` names the shell; `command` is the copyable text. No fake screenshots.
 */
export function TerminalBlock({
  command,
  label = "bash",
  className,
}: {
  command: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border border-border bg-surface-1",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <Terminal className="size-3.5" />
          {label}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? "Copied" : "Copy command"}
          className="flex items-center gap-1.5 rounded-sm px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {copied ? (
            <>
              <Check className="size-3.5 text-success" /> Copied
            </>
          ) : (
            <>
              <Copy className="size-3.5" /> Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3">
        <code className="type-code text-foreground">
          <span className="select-none text-brand">$ </span>
          {command}
        </code>
      </pre>
    </div>
  );
}
