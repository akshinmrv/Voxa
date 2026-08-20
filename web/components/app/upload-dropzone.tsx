"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { UploadCloud, FileVideo, X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ACCEPT = ".mp4,.mov,.mkv,.webm,video/*";

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Drag-and-drop (or click) video picker. Accepts several videos — one job is queued per
 *  file — and is controlled via `files` / `onFiles`. */
export function UploadDropzone({
  files,
  onFiles,
}: {
  files: File[];
  onFiles: (files: File[]) => void;
}) {
  const t = useTranslations("App.newJob");
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function add(picked: FileList | null) {
    const videos = Array.from(picked ?? []).filter((f) => f.type.startsWith("video/"));
    if (!videos.length) return;
    // Same name + size twice is the same pick, not two videos.
    const key = (f: File) => `${f.name}:${f.size}`;
    const seen = new Set(files.map(key));
    onFiles([...files, ...videos.filter((f) => !seen.has(key(f)))]);
  }

  const hidden = (
    <input
      ref={inputRef}
      type="file"
      accept={ACCEPT}
      multiple
      className="hidden"
      onChange={(e) => {
        add(e.target.files);
        e.target.value = ""; // let the same file be re-picked after removal
      }}
    />
  );

  if (files.length > 0) {
    const total = files.reduce((n, f) => n + f.size, 0);
    return (
      <div
        className={cn(
          "space-y-2 rounded-md border p-4 transition-colors",
          dragging ? "border-primary bg-primary/5" : "border-border bg-surface-1",
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
      >
        <div className="flex items-center justify-between">
          <p className="type-label text-muted-foreground">
            {t("selectedFiles", { count: files.length })} · {formatSize(total)}
          </p>
          <Button variant="ghost" size="sm" onClick={() => onFiles([])}>
            <X /> {t("removeAll")}
          </Button>
        </div>

        <ul className="space-y-2">
          {files.map((file) => (
            <li
              key={`${file.name}:${file.size}`}
              className="flex items-center gap-3 rounded-sm border border-border bg-surface-2 p-2.5"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-sm border border-border text-primary">
                <FileVideo className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{file.name}</p>
                <p className="type-code text-xs text-muted-foreground tabular">
                  {formatSize(file.size)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                aria-label={t("remove")}
                onClick={() => onFiles(files.filter((f) => f !== file))}
              >
                <X />
              </Button>
            </li>
          ))}
        </ul>

        <Button variant="ghost" size="sm" onClick={() => inputRef.current?.click()}>
          <Plus /> {t("addMore")}
        </Button>
        {hidden}
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
        add(e.dataTransfer.files);
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
      {hidden}
    </button>
  );
}
