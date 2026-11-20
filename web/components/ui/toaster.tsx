"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Check, Info, PencilLine, X } from "lucide-react";
import { dismissToast, useToasts, type ToastTone } from "@/lib/toast";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

const TONE: Record<ToastTone, { icon: typeof Check; color: string; border: string }> = {
  info: { icon: Info, color: "text-info", border: "border-border" },
  success: { icon: Check, color: "text-success", border: "border-border" },
  warning: { icon: PencilLine, color: "text-warning", border: "border-warning/40" },
  error: { icon: AlertTriangle, color: "text-danger", border: "border-danger/40" },
};

/** The corner the console's notes show in, above the status bar. */
export function Toaster() {
  const t = useTranslations("Common");
  const toasts = useToasts();
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-10 right-4 z-[60] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2"
    >
      {toasts.map((item) => {
        const { icon: Icon, color, border } = TONE[item.tone];
        return (
          <div
            key={item.id}
            role={item.tone === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex items-start gap-2.5 rounded-md border bg-surface-3 p-3 text-ui-body text-foreground shadow-overlay animate-voxa-in",
              border,
            )}
          >
            <Icon className={cn("mt-0.5 size-4 shrink-0", color)} aria-hidden />
            <div className="min-w-0 flex-1 space-y-1.5">
              <p className="break-words">{item.text}</p>
              {item.action && (
                <Link
                  href={item.action.href}
                  onClick={() => dismissToast(item.id)}
                  className="inline-flex text-ui-small font-medium text-primary hover:underline"
                >
                  {item.action.label}
                </Link>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(item.id)}
              aria-label={t("close")}
              className="-m-1 rounded-sm p-1 text-muted-foreground transition-colors duration-(--dur-1) hover:bg-surface-2 hover:text-foreground"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </div>
        );
      })}
    </div>
  );
}
