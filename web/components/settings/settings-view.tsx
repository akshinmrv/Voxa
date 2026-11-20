"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import {
  AudioLines,
  Gauge,
  Info,
  Languages,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Users,
  type LucideIcon,
} from "lucide-react";
import { getKeys, getOptions, getSettings, updateSettings } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useRouter } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BackendError, Loading } from "@/components/app/query-states";
import { LeaveDialog, useLeaveGuard } from "@/components/app/leave-guard";
import { cn } from "@/lib/utils";
import { changes, savedValues, toPatch, type Draft } from "./draft";
import { FlashContext } from "./row";
import {
  AboutSection,
  GeneralSection,
  PerformanceSection,
  ResetSection,
  SpeakersSection,
  SpeechSection,
  TranslationSection,
} from "./sections";

const SECTIONS: { id: SectionId; icon: LucideIcon }[] = [
  { id: "general", icon: SlidersHorizontal },
  { id: "translation", icon: Languages },
  { id: "speech", icon: AudioLines },
  { id: "speakers", icon: Users },
  { id: "performance", icon: Gauge },
  { id: "about", icon: Info },
  { id: "reset", icon: RotateCcw },
];
type SectionId =
  "general" | "translation" | "speech" | "speakers" | "performance" | "about" | "reset";

/** Every setting the search finds: where it is, and the messages it is found by. */
const FIELDS: { id: string; section: SectionId; label: string; hint?: string }[] = [
  { id: "language", section: "general", label: "appearance.language" },
  { id: "theme", section: "general", label: "appearance.theme" },
  {
    id: "autoDownload",
    section: "general",
    label: "advanced.autoDownloadLabel",
    hint: "advanced.autoDownloadHint",
  },
  {
    id: "checkUpdates",
    section: "general",
    label: "advanced.checkUpdatesLabel",
    hint: "advanced.checkUpdatesHint",
  },
  {
    id: "defaultTranslator",
    section: "translation",
    label: "providers.translator",
    hint: "providers.desc",
  },
  {
    id: "fallback",
    section: "translation",
    label: "advanced.fallbackLabel",
    hint: "advanced.fallbackHint",
  },
  { id: "prompt", section: "translation", label: "translation.title", hint: "translation.desc" },
  { id: "defaultTts", section: "speech", label: "providers.tts" },
  {
    id: "qualityGate",
    section: "speech",
    label: "advanced.qualityGateLabel",
    hint: "advanced.qualityGateHint",
  },
  { id: "presets", section: "speech", label: "speech.title", hint: "speech.desc" },
  { id: "instructions", section: "speech", label: "speech.textLabel", hint: "speech.placeholder" },
  { id: "hfToken", section: "speakers", label: "speakers.token", hint: "speakers.desc" },
  {
    id: "device",
    section: "performance",
    label: "advanced.deviceLabel",
    hint: "advanced.deviceHint",
  },
  {
    id: "maxConcurrentJobs",
    section: "performance",
    label: "advanced.concurrentLabel",
    hint: "advanced.concurrentHint",
  },
  {
    id: "ttsWorkers",
    section: "performance",
    label: "advanced.workersLabel",
    hint: "advanced.workersHint",
  },
  {
    id: "speechRate",
    section: "performance",
    label: "advanced.rateLabel",
    hint: "advanced.rateHint",
  },
  { id: "version", section: "about", label: "about.version", hint: "about.updateSearch" },
  { id: "systemCheck", section: "about", label: "about.system", hint: "about.systemHint" },
  { id: "logs", section: "about", label: "about.logs", hint: "about.logsHint" },
  { id: "links", section: "about", label: "about.links", hint: "about.licences" },
  { id: "reset", section: "reset", label: "danger.reset", hint: "danger.desc" },
];

/** Which section a change is in, for the dot by its name. */
const SECTION_OF: Record<string, SectionId> = Object.fromEntries(
  FIELDS.map((f) => [f.id, f.section]),
);

/** Lower case, without accents, so "dil" finds "Dil" and "cihaz" finds "Cihaz". */
function fold(text: string, locale: string) {
  return text
    .toLocaleLowerCase(locale)
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ı/g, "i")
    .replace(/ə/g, "e");
}

/**
 * Settings (VOXA_DESIGN_PLAN.md §8.8): seven sections beside one another, a search over every
 * setting's name and description, and one "Save" for what changed, wherever it is. Keys are
 * saved on their own. The section is in the address (?section=), so other pages link to one.
 */
export function SettingsView() {
  const t = useTranslations("App.settings");
  const locale = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const asked = params.get("section");
  const [section, setSection] = useState<SectionId>(
    SECTIONS.some((s) => s.id === asked) ? (asked as SectionId) : "general",
  );
  const [draft, setDraft] = useState<Draft>({});
  const [query, setQuery] = useState("");
  const [flash, setFlash] = useState<string | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const optionsQuery = useQuery({ queryKey: ["options"], queryFn: getOptions });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const keysQuery = useQuery({ queryKey: ["keys"], queryFn: getKeys, retry: false });

  const providers = useMemo(
    () => keysQuery.data?.keys.map((k) => k.provider) ?? [],
    [keysQuery.data],
  );
  const saved = useMemo(
    () => (settingsQuery.data ? savedValues(settingsQuery.data, providers) : null),
    [settingsQuery.data, providers],
  );
  const changed = useMemo(() => (saved ? changes(draft, saved) : []), [draft, saved]);
  const dirtySections = new Set(
    changed.map((c) => (c.startsWith("models.") ? "translation" : SECTION_OF[c])),
  );

  const save = useMutation({
    mutationFn: () => updateSettings(toPatch(draft, saved!)),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      // The update banner follows "Check for updates" at once, not hours later.
      if (changed.includes("checkUpdates")) void qc.invalidateQueries({ queryKey: ["update"] });
      setDraft({});
      toast(t("savedNote"));
    },
  });

  const guard = useLeaveGuard(changed.length > 0);

  // Ctrl+S saves what changed.
  const saveNow = useRef(() => {});
  useEffect(() => {
    saveNow.current = () => {
      if (changed.length && !save.isPending) save.mutate();
    };
  });
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveNow.current();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // A setting a search led to: brought into view, its control focused.
  useEffect(() => {
    if (!flash) return;
    const row = document.getElementById(`setting-${flash}`);
    row?.scrollIntoView({ block: "center" });
    row
      ?.querySelector<HTMLElement>("input, select, textarea, button, [role=radio]")
      ?.focus({ preventScroll: true });
  }, [flash]);

  const index = useMemo(() => {
    const options = optionsQuery.data;
    const fields = FIELDS.map((f) => ({
      id: f.id,
      section: f.section,
      label: t(f.label as "providers.tts"),
      text: [t(f.label as "providers.tts"), f.hint ? t(f.hint as "providers.desc") : ""].join(" "),
    }));
    // Each key by its provider's name.
    for (const k of keysQuery.data?.keys ?? []) {
      const label = options?.translators.find((tr) => tr.id === k.provider)?.label ?? k.provider;
      fields.push({
        id: `key-${k.provider}`,
        section: "translation",
        label: `${label} · ${t("keys.keyLabel")}`,
        text: `${label} ${k.envKey} ${t("keys.title")}`,
      });
    }
    return fields.map((f) => ({ ...f, folded: fold(f.text, locale) }));
  }, [t, locale, optionsQuery.data, keysQuery.data]);

  const needle = fold(query.trim(), locale);
  const results = needle ? index.filter((f) => f.folded.includes(needle)) : [];

  function show(next: SectionId) {
    setSection(next);
    // Kept in the address, without a navigation, so a reload or a link comes back here.
    window.history.replaceState(null, "", `?section=${next}`);
    document.getElementById("main-content")?.scrollTo(0, 0);
  }

  function go(field: { id: string; section: SectionId }) {
    show(field.section);
    setQuery("");
    setFlash(field.id);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), 1800);
  }

  function changeLanguage(next: string) {
    if (next === locale) return;
    if (changed.length) guard.ask(`/${next}/app/settings/?section=${section}`);
    else router.replace({ pathname: "/app/settings", query: { section } }, { locale: next });
  }

  if (optionsQuery.isPending || settingsQuery.isPending) return <Loading />;
  if (!optionsQuery.data || !settingsQuery.data || !saved)
    return (
      <BackendError
        onRetry={() => {
          optionsQuery.refetch();
          settingsQuery.refetch();
        }}
      />
    );

  const values = {
    ...saved,
    ...draft,
    models: { ...saved.models, ...draft.models },
  };
  const props = {
    values,
    set: (patch: Draft) => setDraft((d) => ({ ...d, ...patch })),
    options: optionsQuery.data,
    keys: keysQuery.data,
  };
  const current = SECTIONS.find((s) => s.id === section)!;

  return (
    <div className="grid gap-6 md:grid-cols-[13rem_minmax(0,1fr)] lg:gap-10">
      <nav aria-label={t("title")} className="space-y-3 md:sticky md:top-0 md:self-start">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
            aria-hidden
          />
          <Input
            type="search"
            aria-label={t("search")}
            placeholder={t("search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) {
                e.preventDefault();
                go(results[0]);
              }
            }}
            className="h-8 pl-8 text-ui-body"
          />
        </div>
        {needle ? (
          <ul aria-label={t("results")} className="space-y-0.5">
            {results.length === 0 && (
              <li className="px-2 py-1.5 text-ui-small text-muted-foreground">{t("noResults")}</li>
            )}
            {results.slice(0, 12).map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => go(r)}
                  className="w-full rounded-sm px-2 py-1.5 text-left transition-colors duration-(--dur-1) hover:bg-surface-2"
                >
                  <span className="block truncate text-ui-body">{r.label}</span>
                  <span className="block text-ui-small text-muted-foreground">
                    {t(`sections.${r.section}`)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="flex flex-wrap gap-1 md:block md:space-y-0.5">
            {SECTIONS.map(({ id, icon: Icon }) => (
              <li key={id}>
                <button
                  type="button"
                  aria-current={id === section ? "page" : undefined}
                  onClick={() => show(id)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-sm px-2 py-1.5 text-left text-ui-body transition-colors duration-(--dur-1) [&_svg]:size-4 [&_svg]:shrink-0",
                    id === section
                      ? "bg-surface-2 text-foreground"
                      : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
                    id === "reset" && "md:mt-3",
                  )}
                >
                  <Icon aria-hidden className={id === "reset" ? "text-danger" : undefined} />
                  <span className="flex-1">{t(`sections.${id}`)}</span>
                  {dirtySections.has(id) && (
                    <span
                      className="size-1.5 rounded-full bg-primary"
                      title={t("unsavedHere")}
                      aria-label={t("unsavedHere")}
                    />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>

      <div className="min-w-0 max-w-3xl space-y-6">
        <header>
          <h2 className="text-ui-section">{t(`sections.${current.id}`)}</h2>
          <p className="mt-1 text-ui-small text-muted-foreground">
            {t(`sectionDesc.${current.id}`)}
          </p>
        </header>
        <FlashContext.Provider value={flash}>
          {section === "general" && <GeneralSection {...props} onLanguage={changeLanguage} />}
          {section === "translation" && <TranslationSection {...props} />}
          {section === "speech" && <SpeechSection {...props} />}
          {section === "speakers" && <SpeakersSection {...props} />}
          {section === "performance" && <PerformanceSection {...props} />}
          {section === "about" && <AboutSection />}
          {section === "reset" && <ResetSection onReset={() => setDraft({})} />}
        </FlashContext.Provider>

        {changed.length > 0 && (
          <div
            role="region"
            aria-label={t("unsaved")}
            className="sticky bottom-0 z-20 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface-3 px-4 py-3 shadow-overlay animate-voxa-in"
          >
            <span className="text-ui-body font-medium" aria-live="polite">
              {t("changes", { count: changed.length })}
            </span>
            {save.isError && (
              <span className="min-w-0 text-ui-small text-danger">
                {(save.error as Error).message}
              </span>
            )}
            <span className="flex-1" />
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setDraft({})}
              disabled={save.isPending}
            >
              {t("discard")}
            </Button>
            <Button size="sm" onClick={() => save.mutate()} loading={save.isPending}>
              {t("saveChanges")}
            </Button>
          </div>
        )}
      </div>

      <LeaveDialog
        guard={guard}
        title={t("leaveTitle")}
        body={t("leaveBody", { count: Math.max(changed.length, 1) })}
        stayLabel={t("stay")}
        leaveLabel={t("leave")}
        onForget={() => setDraft({})}
      />
    </div>
  );
}
