"use client";

import { useTranslations } from "next-intl";
import { useDesktop } from "@/lib/desktop";
import { SHORTCUTS, keyLabel } from "@/lib/shortcuts";
import { Kbd } from "@/components/ui/kbd";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** "?": every shortcut, read from the same list the keys are handled from. */
export function ShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("App.shell.shortcuts");
  const common = useTranslations("Common");
  const desktop = useDesktop();
  // In a browser the window's own shortcuts (Ctrl+N, Ctrl+1…) belong to the browser.
  const shown = SHORTCUTS.filter((s) => desktop || !s.desktopOnly);
  const hidden = SHORTCUTS.length - shown.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={common("close")} className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          {hidden > 0 && <DialogDescription>{t("desktopOnly")}</DialogDescription>}
        </DialogHeader>
        <dl className="divide-y divide-border">
          {shown.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-4 py-2">
              <dt className="text-ui-body">{t(s.id)}</dt>
              <dd>
                <Kbd>{keyLabel(s.keys)}</Kbd>
              </dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
