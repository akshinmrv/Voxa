"use client";

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { cancelJob, deleteJob, getHealth, retryJob, revealFile } from "@/lib/api";
import { useDesktop } from "@/lib/desktop";
import { STUDIO_CHOICE_KEY, choiceFromJob } from "@/lib/job-config";
import { toast } from "@/lib/toast";
import type { JobConfig, JobSummary } from "@/lib/types";
import { useRouter } from "@/i18n/navigation";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

// What can be done to a dub, from its page and from the list alike (VOXA_DESIGN_PLAN.md §7.3):
// stop it, take it off the list, show its files, start another with its settings.

export type RevealKind = "video" | "srt" | "folder";

/** What "Show in folder" points at: the dub, else its subtitles, else the folder it works in. */
export function revealTarget(job: Pick<JobSummary, "status" | "hasVideo" | "hasSrt">): RevealKind {
  if (job.status === "done" && job.hasVideo) return "video";
  if (job.status === "done" && job.hasSrt) return "srt";
  return "folder";
}

/**
 * Whether the server can show files in a folder for this console: it runs on this machine,
 * which has a desktop. Not in a container, nor for a console on another machine.
 */
export function useCanReveal(): boolean | null {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false });
  // null until the server has said: a button that could still turn into another stays out.
  return health.data ? !!health.data.canReveal : null;
}

export function useReveal() {
  const t = useTranslations("App.library");
  const desktop = useDesktop();
  return useMutation({
    mutationFn: async ({ id, file }: { id: string; file: RevealKind }) => {
      // In Voxa Studio's window, which is in front now, so Explorer's opens over it.
      await desktop?.let_explorer_front?.().catch(() => false);
      return revealFile(id, file);
    },
    onError: (error) => toast(t("revealFailed", { reason: (error as Error).message }), "error"),
  });
}

/** Run a failed or stopped dub again, in place; then `onStarted`, to follow its run. */
export function useRetry(onStarted?: (id: string) => void) {
  const t = useTranslations("App.library");
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryJob(id),
    onSuccess: (job) => {
      queryClient.setQueryData(["job", job.id], job);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      onStarted?.(job.id);
    },
    onError: (error) => toast(t("retryFailed", { reason: (error as Error).message }), "error"),
  });
}

/** Open the Studio with a dub's settings, to make another from them. */
export function useOpenInStudio() {
  const router = useRouter();
  return useCallback(
    (config: JobConfig) => {
      try {
        window.sessionStorage.setItem(STUDIO_CHOICE_KEY, JSON.stringify(choiceFromJob(config)));
      } catch {
        /* the Studio opens with its own defaults */
      }
      router.push("/app");
    },
    [router],
  );
}

type Removable = Pick<JobSummary, "id" | "fileName" | "status" | "hasVideo" | "hasSrt">;

/**
 * Stopping and removing, with the questions they ask first. One pair of dialogs serves a
 * whole list: askStop / askRemove say which dub they are for.
 */
export function useJobDialogs({
  onStopped,
  onRemoved,
}: { onStopped?: (id: string) => void; onRemoved?: (id: string) => void } = {}) {
  const t = useTranslations("App.job");
  const tl = useTranslations("App.library");
  const common = useTranslations("Common");
  const queryClient = useQueryClient();
  const [stopping, setStopping] = useState<string | null>(null);
  const [removing, setRemoving] = useState<Removable | null>(null);
  const [withFiles, setWithFiles] = useState(false);

  function refresh(id: string) {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["job", id] });
  }

  const stop = useMutation({
    mutationFn: (id: string) => cancelJob(id),
    onError: (error) => toast(tl("stopFailed", { reason: (error as Error).message }), "error"),
    onSettled: (_data, _error, id) => {
      refresh(id);
      onStopped?.(id);
    },
  });

  const remove = useMutation({
    mutationFn: ({ job, files }: { job: Removable; files: boolean }) => deleteJob(job.id, files),
    onSuccess: ({ removedFiles }, { job, files }) => {
      setRemoving(null);
      setWithFiles(false);
      // Not its own query: its page, if open, would ask again and be told it's gone.
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      const name = job.fileName;
      // What happened, exactly: kept files are said, so nobody looks for them in vain.
      const made = job.status === "done" && (job.hasVideo || job.hasSrt);
      toast(
        !made
          ? tl("removedOnly", { name })
          : !files
            ? tl("removed", { name })
            : removedFiles.length
              ? tl("removedWithFiles", { name, count: removedFiles.length })
              : tl("removedKeptFiles", { name }),
        "success",
      );
      onRemoved?.(job.id);
    },
  });

  // Stable, so a list's rows (memoized) aren't all drawn again when one of them changes.
  const askStop = useCallback((id: string) => setStopping(id), []);
  const stopIt = stop.mutate;
  const stopNow = useCallback((id: string) => stopIt(id), [stopIt]);
  const askRemove = useCallback((job: Removable) => setRemoving(job), []);

  const hasFiles =
    !!removing && removing.status === "done" && (removing.hasVideo || removing.hasSrt);

  const dialogs = (
    <>
      <AlertDialog open={stopping !== null} onOpenChange={(open) => !open && setStopping(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("stopTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("stopBody")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive
              onClick={() => {
                if (stopping) stop.mutate(stopping);
              }}
            >
              {t("stop")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={removing !== null}
        onOpenChange={(open) => {
          if (open) return;
          setRemoving(null);
          setWithFiles(false);
          remove.reset();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("removeTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {hasFiles ? t("removeBody") : tl("removeBodyNoFiles")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {removing && <p className="truncate font-mono text-ui-mono">{removing.fileName}</p>}
          {hasFiles && (
            <label className="flex items-center gap-2.5 text-ui-body">
              <input
                type="checkbox"
                checked={withFiles}
                onChange={(e) => setWithFiles(e.target.checked)}
                className="size-4 accent-[var(--destructive)]"
              />
              {t("removeFiles")}
            </label>
          )}
          {remove.isError && (
            <p className="text-ui-small text-danger">{(remove.error as Error).message}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive
              disabled={remove.isPending}
              onClick={(e) => {
                e.preventDefault(); // stays open until it's done, to show an error
                if (removing) remove.mutate({ job: removing, files: hasFiles && withFiles });
              }}
            >
              {t("removeConfirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );

  return {
    askStop,
    /** A queued dub has nothing to lose: stopped without asking. */
    stopNow,
    askRemove,
    /** The dub being stopped now, if any. */
    stoppingId: stop.isPending ? (stop.variables ?? null) : null,
    dialogs,
  };
}
