"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { FileVideo, Link2, Plus, UploadCloud, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented";
import { cn } from "@/lib/utils";

const ACCEPT = ".mp4,.mov,.mkv,.webm,video/*";

export const fileKey = (file: File) => `${file.name}:${file.size}`;

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

export function formatDuration(seconds: number) {
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${rest}` : `${m}:${rest}`;
}

/**
 * Each video's length, read here from its metadata (no upload needed). A format this browser
 * can't open (an MKV with HEVC in it, say) has none: null, shown as "—".
 */
export function useDurations(files: File[]): Record<string, number | null> {
  const [durations, setDurations] = useState<Record<string, number | null>>({});
  // Each file is measured once, however often the list changes while it's being read.
  const [asked] = useState(() => new Set<string>());
  useEffect(() => {
    for (const file of files) {
      const key = fileKey(file);
      if (asked.has(key)) continue;
      asked.add(key);
      const url = URL.createObjectURL(file);
      const video = document.createElement("video");
      video.preload = "metadata";
      const done = (value: number | null) => {
        setDurations((d) => ({ ...d, [key]: value }));
        URL.revokeObjectURL(url);
        video.removeAttribute("src");
      };
      video.onloadedmetadata = () => done(Number.isFinite(video.duration) ? video.duration : null);
      video.onerror = () => done(null);
      video.src = url;
    }
  }, [files, asked]);
  return durations;
}

export type SourceMode = "file" | "url";

/** The videos to dub: dropped or chosen files, or a link yt-dlp can fetch. */
export function SourcePicker({
  mode,
  onMode,
  urlAvailable,
  files,
  onFiles,
  url,
  onUrl,
  durations,
  inputRef,
}: {
  mode: SourceMode;
  onMode: (mode: SourceMode) => void;
  urlAvailable: boolean;
  files: File[];
  onFiles: (files: File[]) => void;
  url: string;
  onUrl: (url: string) => void;
  durations: Record<string, number | null>;
  inputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const t = useTranslations("App.newJob");
  const [dragging, setDragging] = useState(false);

  function add(picked: FileList | null) {
    const videos = Array.from(picked ?? []).filter(
      (f) => f.type.startsWith("video/") || /\.(mp4|mov|mkv|webm)$/i.test(f.name),
    );
    if (!videos.length) return;
    const seen = new Set(files.map(fileKey));
    onFiles([...files, ...videos.filter((f) => !seen.has(fileKey(f)))]);
    onMode("file");
  }

  const drop = {
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(true);
    },
    onDragLeave: () => setDragging(false),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      add(e.dataTransfer.files);
    },
  };

  const input = (
    <input
      ref={inputRef}
      type="file"
      accept={ACCEPT}
      multiple
      className="hidden"
      onChange={(e) => {
        add(e.target.files);
        e.target.value = ""; // the same file can be chosen again after it's removed
      }}
    />
  );

  return (
    <div className="space-y-3">
      {urlAvailable && (
        <SegmentedControl
          aria-label={t("sourceFile")}
          size="sm"
          value={mode}
          onValueChange={onMode}
          items={[
            { value: "file", label: t("sourceFile"), icon: <FileVideo /> },
            { value: "url", label: t("sourceUrl"), icon: <Link2 /> },
          ]}
        />
      )}

      {mode === "url" && urlAvailable ? (
        <div className="space-y-2">
          <label htmlFor="source-url" className="text-ui-body font-medium">
            {t("urlLabel")}
          </label>
          <Input
            id="source-url"
            type="url"
            inputMode="url"
            placeholder="https://…"
            value={url}
            onChange={(e) => onUrl(e.target.value)}
          />
          <p className="text-ui-small text-muted-foreground">{t("urlHint")}</p>
          <p className="text-ui-small text-muted-foreground">{t("urlTos")}</p>
        </div>
      ) : files.length === 0 ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          {...drop}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center transition-colors duration-(--dur-1)",
            dragging
              ? "border-primary bg-brand-tint"
              : "border-border-strong bg-surface-1 hover:border-primary/60",
          )}
        >
          <span className="flex size-12 items-center justify-center rounded-md border border-border bg-surface-2 text-primary">
            <UploadCloud className="size-6" aria-hidden />
          </span>
          <span>
            <span className="block text-ui-section">{t("uploadTitle")}</span>
            <span className="mt-1 block text-ui-small text-muted-foreground">
              {t("uploadHint")}
            </span>
          </span>
          {input}
        </button>
      ) : (
        <div
          {...drop}
          className={cn(
            "rounded-lg border p-2 transition-colors duration-(--dur-1)",
            dragging ? "border-primary bg-brand-tint" : "border-border bg-surface-1",
          )}
        >
          <ul className="divide-y divide-border">
            {files.map((file) => {
              const seconds = durations[fileKey(file)];
              return (
                <li key={fileKey(file)} className="flex items-center gap-3 px-2 py-2">
                  <FileVideo className="size-4 shrink-0 text-primary" aria-hidden />
                  <span className="min-w-0 flex-1 truncate text-ui-body" title={file.name}>
                    {file.name}
                  </span>
                  <span className="font-mono text-ui-mono tabular text-muted-foreground">
                    {seconds == null ? "—" : formatDuration(seconds)}
                  </span>
                  <span className="hidden w-20 text-right font-mono text-ui-mono tabular text-fg-subtle sm:block">
                    {formatSize(file.size)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`${t("remove")}: ${file.name}`}
                    onClick={() => onFiles(files.filter((f) => f !== file))}
                  >
                    <X />
                  </Button>
                </li>
              );
            })}
          </ul>
          <div className="flex items-center justify-between gap-2 border-t border-border px-1 pt-2">
            <Button variant="ghost" size="sm" onClick={() => inputRef.current?.click()}>
              <Plus /> {t("addMore")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onFiles([])}>
              {t("removeAll")}
            </Button>
          </div>
          {input}
        </div>
      )}
    </div>
  );
}
