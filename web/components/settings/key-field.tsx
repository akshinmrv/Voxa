"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Check, ExternalLink, Eye, EyeOff, PlugZap, Trash2, X } from "lucide-react";
import { deleteKey, putKey, testProvider } from "@/lib/api";
import type { KeysStatus, ProviderKeyStatus, ProviderTestResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { cn } from "@/lib/utils";

type KeyStatus = Pick<ProviderKeyStatus, "envKey" | "hasKey" | "masked" | "source">;

/**
 * One key: shown only masked, with where it comes from (the .env Settings writes, or the
 * environment Voxa was started in), tested against its own provider, replaced or removed.
 * Each key is saved on its own, at once: never part of the page's "Save". The value typed
 * goes up once and never comes back to the page.
 */
export function KeyField({
  provider,
  label,
  status,
  placeholder,
  children,
}: {
  /** An LLM provider's id, or "hf" for the Hugging Face token. */
  provider: string;
  label: string;
  status: KeyStatus;
  /** What the empty field asks for, when it isn't an API key. */
  placeholder?: string;
  /** More for this key, under it: a default model, a test's details. */
  children?: (test: ProviderTestResult | undefined) => React.ReactNode;
}) {
  const t = useTranslations("App.settings.keys");
  const common = useTranslations("Common");
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const [askRemove, setAskRemove] = useState(false);

  const refresh = (data: KeysStatus) => qc.setQueryData(["keys"], data);
  const test = useMutation({ mutationFn: () => testProvider(provider) });
  const save = useMutation({
    mutationFn: () => putKey(provider, value.trim()),
    onSuccess: (data) => {
      refresh(data);
      setValue("");
      setShow(false);
      setEditing(false);
      test.reset();
      // `voxa doctor` and the System page see it at once.
      void qc.invalidateQueries({ queryKey: ["doctor"] });
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteKey(provider),
    onSuccess: (data) => {
      refresh(data);
      setAskRemove(false);
      test.reset();
      void qc.invalidateQueries({ queryKey: ["doctor"] });
    },
  });

  const open = editing || !status.hasKey;
  const fromEnvironment = status.source === "environment";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="text-ui-body font-medium">{label}</span>
        {status.hasKey ? (
          <>
            <span className="font-mono text-ui-mono text-foreground">{status.masked}</span>
            <Badge
              variant="neutral"
              title={fromEnvironment ? t("sourceEnvHint", { name: status.envKey }) : undefined}
            >
              {t(fromEnvironment ? "source.environment" : "source.file")}
            </Badge>
          </>
        ) : (
          <span className="text-ui-small text-muted-foreground">{t("notSet")}</span>
        )}
        <span className="flex-1" />
        {status.hasKey && (
          <span className="flex flex-wrap gap-1">
            <Button
              size="xs"
              variant="secondary"
              onClick={() => test.mutate()}
              loading={test.isPending}
            >
              {!test.isPending && <PlugZap />} {test.isPending ? t("testing") : t("test")}
            </Button>
            {!editing && (
              <Button size="xs" variant="ghost" onClick={() => setEditing(true)}>
                {t("replace")}
              </Button>
            )}
            <Button size="xs" variant="ghost" onClick={() => setAskRemove(true)}>
              <Trash2 /> {t("deleteKey")}
            </Button>
          </span>
        )}
      </div>

      {open && (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) save.mutate();
          }}
        >
          <Input
            id={`key-${provider}`}
            type={show ? "text" : "password"}
            autoComplete="off"
            spellCheck={false}
            value={value}
            aria-label={t("keyFor", { label })}
            placeholder={
              status.hasKey ? t("keyPlaceholderSet") : (placeholder ?? t("keyPlaceholderEmpty"))
            }
            onChange={(e) => setValue(e.target.value)}
            className="h-8 font-mono text-ui-mono"
          />
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={show ? t("hide") : t("show")}
            onClick={() => setShow((s) => !s)}
          >
            {show ? <EyeOff /> : <Eye />}
          </Button>
          <Button type="submit" size="sm" disabled={!value.trim()} loading={save.isPending}>
            {t("saveKey")}
          </Button>
          {editing && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setEditing(false);
                setValue("");
              }}
            >
              {common("cancel")}
            </Button>
          )}
        </form>
      )}
      {save.isError && <p className="text-ui-small text-danger">{(save.error as Error).message}</p>}

      {test.data && <TestResult result={test.data} />}
      {test.isError && <p className="text-ui-small text-danger">{t("testFail")}</p>}
      {children?.(test.data)}

      <AlertDialog open={askRemove} onOpenChange={setAskRemove}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("removeTitle", { label })}</AlertDialogTitle>
            <AlertDialogDescription>
              {fromEnvironment
                ? t("removeBodyEnv", { label, name: status.envKey })
                : t("removeBody", { label })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {remove.isError && (
            <p className="text-ui-small text-danger">{(remove.error as Error).message}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              destructive
              disabled={remove.isPending}
              onClick={(e) => {
                e.preventDefault();
                remove.mutate();
              }}
            >
              {t("deleteKey")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** What a test found: connected (and how fast), or why not; for Hugging Face, each model. */
function TestResult({ result }: { result: ProviderTestResult }) {
  const t = useTranslations("App.settings.keys");
  return (
    <div className="space-y-1.5 text-ui-small" role="status">
      {result.ok ? (
        <p className="inline-flex items-center gap-1.5 text-success">
          <Check className="size-4" />{" "}
          {result.user ? t("testOkUser", { user: result.user }) : t("testOk")}
          {typeof result.latencyMs === "number" && (
            <span className="text-fg-subtle">· {result.latencyMs} ms</span>
          )}
        </p>
      ) : result.error ? (
        <p className="inline-flex items-center gap-1.5 text-danger">
          <X className="size-4 shrink-0" /> {result.error}
        </p>
      ) : result.user ? (
        <p className="text-muted-foreground">{t("testOkUser", { user: result.user })}</p>
      ) : null}
      {result.models && (
        <ul className="space-y-1">
          {result.models.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-x-2">
              {m.access ? (
                <Check className="size-4 text-success" aria-hidden />
              ) : (
                <X
                  className={cn("size-4", m.access === false ? "text-danger" : "text-warning")}
                  aria-hidden
                />
              )}
              <span className="font-mono text-ui-mono">{m.id}</span>
              <span className={m.access ? "text-muted-foreground" : "text-foreground"}>
                {m.access ? t("access") : m.access === false ? t("noAccess") : t("accessUnknown")}
              </span>
              {!m.access && (
                <a
                  href={m.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {t("acceptTerms")} <ExternalLink className="size-3" aria-hidden />
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
