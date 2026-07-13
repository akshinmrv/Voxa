"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { UploadCloud, FileVideo, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ACCEPT = ".mp4,.mov,.mkv,.webm,video/*";

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Drag-and-drop (or click) video picker. Controlled via `file` / `onFile`. */
export function UploadDropzone({
  file,
  onFile,
}: {
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  const t = useTranslations("App.newJob");
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function pick(files: FileList | null) {
    const f = files?.[0];
    if (f && f.type.startsWith("video/")) onFile(f);
  }

  if (file) {
    return (
      <div className="flex items-center gap-4 rounded-md border border-border bg-surface-1 p-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-2 text-primary">
          <FileVideo className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="type-label text-muted-foreground">{t("selectedFile")}</p>
          <p className="truncate text-sm font-medium">{file.name}</p>
          <p className="type-code text-xs text-muted-foreground tabular">
            {formatSize(file.size)}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onFile(null)}
          aria-label={t("remove")}
        >
          <X /> {t("remove")}
        </Button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        pick(e.dataTransfer.files);
      }}
      className={cn(
        "flex w-full flex-col items-center justify-center gap-3 rounded-md border border-dashed p-10 text-center transition-colors",
        dragging
          ? "border-primary bg-primary/5"
          : "border-border bg-surface-1 hover:border-primary/40",
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-md border border-border bg-surface-2 text-primary">
        <UploadCloud className="size-6" />
      </div>
      <div>
        <p className="text-sm font-medium">{t("uploadTitle")}</p>
        <p className="mt-1 text-xs text-muted-foreground">{t("uploadHint")}</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => pick(e.target.files)}
      />
    </button>
  );
}
