"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Check, Eye, EyeOff, Loader2, PlugZap, Trash2, X } from "lucide-react";
import { putKey, deleteKey, updateSettings, testProvider } from "@/lib/api";
import type { ProviderKeyStatus } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

/**
 * One provider's key + default-model + connection test (P1). Self-contained: owns its
 * own mutations and invalidates the shared ["keys"] / ["settings"] queries on success.
 * The raw key is only ever sent upward via PUT — it is never rendered back.
 */
export function ProviderCard({
  providerId,
  label,
  defaultModel,
  status,
  savedModel,
}: {
  providerId: string;
  label: string;
  defaultModel?: string;
  status: ProviderKeyStatus;
  savedModel: string | null;
}) {
  const t = useTranslations("App.settings.keys");
  const qc = useQueryClient();

  const [keyDraft, setKeyDraft] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [modelDraft, setModelDraft] = useState(savedModel ?? "");

  const refreshKeys = (data: { keys: ProviderKeyStatus[] }) => qc.setQueryData(["keys"], data);

  const saveKey = useMutation({
    mutationFn: () => putKey(providerId, keyDraft.trim()),
    onSuccess: (data) => {
      refreshKeys(data);
      setKeyDraft("");
      setShowKey(false);
      test.reset();
    },
  });

  const removeKey = useMutation({
    mutationFn: () => deleteKey(providerId),
    onSuccess: (data) => {
      refreshKeys(data);
      test.reset();
    },
  });

  const saveModel = useMutation({
    mutationFn: () =>
      updateSettings({ providers: { [providerId]: { model: modelDraft.trim() || null } } }),
    onSuccess: (data) => qc.setQueryData(["settings"], data),
  });

  const test = useMutation({ mutationFn: () => testProvider(providerId) });

  const keyDirty = keyDraft.trim().length > 0;
  const modelDirty = modelDraft.trim() !== (savedModel ?? "");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{label}</CardTitle>
          {status.hasKey ? (
            <Badge variant="success">
              <Check /> {status.masked}
            </Badge>
          ) : (
            <Badge variant="outline">{t("notSet")}</Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* API key */}
        <Field id={`${providerId}-key`} label={t("keyLabel")}>
          <div className="flex gap-2">
            <Input
              id={`${providerId}-key`}
              type={showKey ? "text" : "password"}
              autoComplete="off"
              value={keyDraft}
              placeholder={status.hasKey ? t("keyPlaceholderSet") : t("keyPlaceholderEmpty")}
              onChange={(e) => setKeyDraft(e.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={showKey ? t("hide") : t("show")}
              onClick={() => setShowKey((v) => !v)}
            >
              {showKey ? <EyeOff /> : <Eye />}
            </Button>
          </div>
          <div className="mt-2 flex gap-2">
            <Button size="sm" disabled={!keyDirty || saveKey.isPending} onClick={() => saveKey.mutate()}>
              {saveKey.isPending ? <Loader2 className="animate-spin" /> : null}
              {t("saveKey")}
            </Button>
            {status.hasKey && (
              <Button
                size="sm"
                variant="outline"
                disabled={removeKey.isPending}
                onClick={() => removeKey.mutate()}
              >
                <Trash2 /> {t("deleteKey")}
              </Button>
            )}
          </div>
          {saveKey.isError && (
            <p className="mt-2 text-xs text-danger">{(saveKey.error as Error).message}</p>
          )}
        </Field>

        {/* Default translation model */}
        <Field id={`${providerId}-model`} label={t("modelLabel")}>
          <div className="flex gap-2">
            <Input
              id={`${providerId}-model`}
              value={modelDraft}
              placeholder={defaultModel}
              onChange={(e) => setModelDraft(e.target.value)}
            />
            <Button
              size="sm"
              variant="secondary"
              disabled={!modelDirty || saveModel.isPending}
              onClick={() => saveModel.mutate()}
            >
              {saveModel.isPending ? <Loader2 className="animate-spin" /> : null}
              {t("saveModel")}
            </Button>
          </div>
        </Field>

        {/* Connection test */}
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="secondary"
            disabled={!status.hasKey || test.isPending}
            onClick={() => test.mutate()}
          >
            {test.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />}
            {test.isPending ? t("testing") : t("test")}
          </Button>
          {test.data?.ok && (
            <span className="inline-flex items-center gap-1.5 text-sm text-success">
              <Check className="size-4" /> {t("testOk")}
              {typeof test.data.latencyMs === "number" && (
                <span className="text-fg-subtle">· {test.data.latencyMs}ms</span>
              )}
            </span>
          )}
          {test.data && !test.data.ok && (
            <span className="inline-flex items-center gap-1.5 text-sm text-danger">
              <X className="size-4" /> {test.data.error ?? t("testFail")}
            </span>
          )}
          {test.isError && <span className="text-sm text-danger">{t("testFail")}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
