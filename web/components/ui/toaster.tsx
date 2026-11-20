"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Check, X } from "lucide-react";
import { dismissToast, useToasts } from "@/lib/toast";
import { cn } from "@/lib/utils";

/** The corner the console's notes show in, above the status bar. */
export function Toaster() {
  const t = useTranslations("Common");
  const toasts = useToasts();
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-10 right-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2"
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          role={item.tone === "error" ? "alert" : "status"}
          className={cn(
            "pointer-events-auto flex items-start gap-2.5 rounded-md border bg-surface-3 p-3 text-ui-body text-foreground shadow-overlay animate-voxa-in",
            item.tone === "error" ? "border-danger/40" : "border-border",
          )}
        >
          {item.tone === "error" ? (
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
          ) : (
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
          )}
          <p className="min-w-0 flex-1 break-words">{item.text}</p>
          <button
            type="button"
            onClick={() => dismissToast(item.id)}
            aria-label={t("close")}
            className="-m-1 rounded-sm p-1 text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-2 hover:text-foreground"
          >
            <X className="size-3.5" aria-hidden />
          </button>
        </div>
      ))}
    </div>
  );
}
