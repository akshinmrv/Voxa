"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Copies `text`, and says so for a moment. */
export function CopyButton({ text, label }: { text: string; label?: string }) {
  const t = useTranslations("Common");
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* no clipboard: the text is there to select */
    }
  }
  return (
    <Button
      type="button"
      size="icon-sm"
      variant="ghost"
      className="size-7 shrink-0"
      onClick={copy}
      aria-label={label ?? t("copy")}
      title={copied ? t("copied") : (label ?? t("copy"))}
    >
      {copied ? <Check className="text-success" /> : <Copy />}
    </Button>
  );
}
