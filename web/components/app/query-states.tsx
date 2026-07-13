"use client";

import { WifiOff, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

/** Shown when the backend can't be reached (server not running). */
export function BackendError({ onRetry }: { onRetry?: () => void }) {
  const t = useTranslations("App.errors");
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-border bg-surface-1 px-6 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-md border border-border bg-surface-2 text-warning">
        <WifiOff className="size-6" />
      </div>
      <p className="mt-4 max-w-sm text-sm text-muted-foreground">
        {t("backendDown")}
      </p>
      {onRetry && (
        <Button variant="secondary" className="mt-6" onClick={onRetry}>
          {t("retry")}
        </Button>
      )}
    </div>
  );
}

/** Centered spinner for loading states. */
export function Loading() {
  const t = useTranslations("App.errors");
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
      <Loader2 className="size-5 animate-spin" />
      <span className="text-sm">{t("loading")}</span>
    </div>
  );
}
