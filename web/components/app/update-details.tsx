"use client";

import { useTranslations } from "next-intl";
import { Download, ExternalLink } from "lucide-react";
import type { UpdateStatus } from "@/lib/types";
import { TerminalBlock } from "@/components/patterns/terminal-block";

/**
 * How this install gets the newer Voxa: the new VoxaSetup.exe for an install it made, else
 * the one command for this kind of install; and the release's notes. Shown by the status
 * bar's update item and by Settings › About.
 */
export function UpdateDetails({ update }: { update: UpdateStatus }) {
  const tu = useTranslations("App.update");
  return (
    <div className="space-y-3">
      {update.download ? (
        <>
          <a
            href={update.download}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-8 items-center gap-2 rounded-sm bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Download className="size-4" /> {tu("download")}
          </a>
          <p className="text-ui-small text-muted-foreground">{tu("setupHint")}</p>
        </>
      ) : update.command ? (
        <>
          <p className="text-ui-small text-muted-foreground">
            {update.kind === "container"
              ? tu("containerHint")
              : update.kind === "source"
                ? tu("sourceHint")
                : tu("commandHint")}
          </p>
          <TerminalBlock label={tu("terminal")} command={update.command} />
        </>
      ) : null}
      {update.notes && (
        <a
          href={update.notes}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-ui-small text-primary hover:underline"
        >
          {tu("whatsNew")} <ExternalLink className="size-3.5" />
        </a>
      )}
    </div>
  );
}
