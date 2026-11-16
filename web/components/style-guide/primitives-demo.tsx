"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  FileVideo,
  FolderOpen,
  KeyRound,
  Loader2,
  MoreHorizontal,
  Play,
  Search,
  Trash2,
  Volume2,
  WifiOff,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { SegmentedControl } from "@/components/ui/segmented";
import { ChoiceCard, ChoiceCards } from "@/components/ui/choice-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Kbd } from "@/components/ui/kbd";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface-1 p-5">
      <h3 className="text-ui-section">{title}</h3>
      {children}
    </div>
  );
}

// What a dub's log looks like, so the scroll area has something real to scroll.
const LOG = [
  "[1/7] Extracting audio...",
  "[2/7] Enhancing audio (noise reduction)...",
  "[3/7] (0:04) Transcribing with Whisper (turbo, cpu)...",
  "[3/7] ✓ 42 segments, en",
  "[4/7] Merging segments into sentences...",
  "[5/7] (0:51) Translating to de with google...",
  "⚠️  Google answered 429 (too many requests); trying again in 2 s",
  "[5/7] ✓ 18 lines",
  "[6/7] (1:02) Synthesizing speech...",
  "[6/7] line 7/18: spoken 1.12× faster to fit",
  "[7/7] (2:40) Assembling final video...",
  "✅ voxa-in-sync_dubbed_de.mp4",
];

export function PrimitivesDemo() {
  const t = useTranslations("App");
  const common = useTranslations("Common");
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<"dub" | "subtitles">("dub");
  const [source, setSource] = useState<"file" | "url">("file");
  const [translator, setTranslator] = useState("google");
  const [toggles, setToggles] = useState({ diarize: true, separate: false, review: false });
  const [theme, setTheme] = useState("dark");
  const steps = t.raw("job.steps") as string[];

  return (
    <TooltipProvider>
      <div className="grid gap-5 lg:grid-cols-2">
        <Block title="Buttons">
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm">
              <Play /> {t("newJob.run")}
            </Button>
            <Button size="sm" variant="secondary">
              {t("newJob.preview", { seconds: 20 })}
            </Button>
            <Button size="sm" variant="outline">
              {t("review.save")}
            </Button>
            <Button size="sm" variant="ghost">
              {t("voices.listen")}
            </Button>
            <Button size="sm" variant="destructive">
              <Trash2 /> {t("voices.delete")}
            </Button>
            <Button size="sm" variant="link">
              {t("nav.docs")}
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="xs">xs</Button>
            <Button size="sm">sm</Button>
            <Button>default</Button>
            <Button size="lg">lg</Button>
            <Tooltip label={common("copy")} shortcut="Ctrl+C">
              <Button size="icon-sm" variant="ghost" aria-label={common("copy")}>
                <Copy />
              </Button>
            </Tooltip>
            <Tooltip label={common("moreActions")}>
              <Button size="icon-sm" variant="outline" aria-label={common("moreActions")}>
                <MoreHorizontal />
              </Button>
            </Tooltip>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" loading={loading} onClick={() => setLoading(true)}>
              <Volume2 /> {t("review.voiceAgain")}
            </Button>
            <Button size="sm" variant="secondary" disabled>
              {t("models.install")}
            </Button>
            <label className="flex items-center gap-2 text-ui-small text-muted-foreground">
              <Switch checked={loading} onCheckedChange={setLoading} /> loading
            </label>
          </div>
        </Block>

        <Block title="Badges & status">
          <div className="flex flex-wrap gap-2">
            <Badge variant="neutral">
              <Clock /> {t("status.queued")}
            </Badge>
            <Badge variant="brand">
              <Loader2 className="animate-spin" /> {t("status.running")}
            </Badge>
            <Badge variant="warning">
              <AlertTriangle /> {t("status.review")}
            </Badge>
            <Badge variant="success">
              <CheckCircle2 /> {t("status.done")}
            </Badge>
            <Badge variant="danger">
              <XCircle /> {t("status.failed")}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="success">
              <WifiOff /> {t("newJob.offlineBadge")}
            </Badge>
            <Badge variant="warning">
              <KeyRound /> {t("newJob.keyBadge")}
            </Badge>
            <Badge variant="outline">{t("models.commercial.yes")}</Badge>
            <Badge variant="outline">{t("models.commercial.no")}</Badge>
          </div>
          <ol className="flex flex-wrap gap-x-4 gap-y-1 text-ui-small text-muted-foreground">
            {steps.map((step, i) => (
              <li key={step}>
                <span className="font-mono text-ui-mono text-fg-subtle">{i + 1}</span> {step}
              </li>
            ))}
          </ol>
        </Block>

        <Block title="Choices">
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl
              aria-label="output"
              value={output}
              onValueChange={setOutput}
              items={[
                { value: "dub", label: t("newJob.outputDub") },
                { value: "subtitles", label: t("newJob.outputSubtitles") },
              ]}
            />
            <SegmentedControl
              aria-label="source"
              size="sm"
              value={source}
              onValueChange={setSource}
              items={[
                { value: "file", label: t("newJob.sourceFile"), icon: <FileVideo /> },
                { value: "url", label: t("newJob.sourceUrl") },
              ]}
            />
          </div>
          <ChoiceCards
            value={translator}
            onValueChange={setTranslator}
            className="xl:grid-cols-2"
            aria-label={t("newJob.translator")}
          >
            <ChoiceCard
              value="google"
              title="Google"
              description="Free, fast, no key required"
            />
            <ChoiceCard
              value="ollama"
              title="Ollama"
              description="Local LLM, fully offline"
              badges={
                <Badge variant="success">
                  <WifiOff /> {t("newJob.offlineBadge")}
                </Badge>
              }
            />
            <ChoiceCard
              value="openai"
              title="OpenAI"
              description="Context-aware, needs API key"
              badges={
                <Badge variant="warning">
                  <KeyRound /> {t("newJob.keyBadge")}
                </Badge>
              }
            />
            <ChoiceCard
              value="chatterbox"
              title="Chatterbox"
              description="Voice cloning in 23 languages"
              disabled
              reason={t("newJob.notInstalled")}
            />
          </ChoiceCards>
          <div className="space-y-3 pt-1">
            {(
              [
                ["diarize", t("newJob.diarizeToggle")],
                ["separate", t("newJob.separateToggle")],
                ["review", t("newJob.reviewToggle")],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-4 text-ui-body">
                {label}
                <Switch
                  checked={toggles[key]}
                  disabled={key === "separate"}
                  onCheckedChange={(on) => setToggles((s) => ({ ...s, [key]: on }))}
                />
              </label>
            ))}
          </div>
        </Block>

        <Block title="Fields (today's controls, for comparison)">
          <Field id="sg-lang" label={t("newJob.targetLang")}>
            <Select id="sg-lang" defaultValue="tr">
              <option value="tr">Turkish (tr)</option>
              <option value="az">Azerbaijani (az)</option>
            </Select>
          </Field>
          <Field id="sg-search" label={common("languageLabel")}>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
              <Input id="sg-search" placeholder="Türkçe, Azərbaycan…" className="pl-9" />
            </div>
          </Field>
          <Textarea aria-label="line" defaultValue="Die meisten Tools setzen jede übersetzte Zeile direkt hinter die vorige." />
        </Block>

        <Block title="Tabs & keys">
          <Tabs defaultValue="lines">
            <TabsList>
              <TabsTrigger value="lines">{t("review.title")}</TabsTrigger>
              <TabsTrigger value="progress">{t("job.progress")}</TabsTrigger>
              <TabsTrigger value="log">{t("job.logs")}</TabsTrigger>
            </TabsList>
            <TabsContent value="lines" className="text-ui-small text-muted-foreground">
              {t("review.editDesc")}
            </TabsContent>
            <TabsContent value="progress" className="text-ui-small text-muted-foreground">
              {steps.join(" → ")}
            </TabsContent>
            <TabsContent value="log">
              <ScrollArea className="h-40 rounded-md border border-border bg-background">
                <pre className="p-3 font-mono text-ui-mono text-muted-foreground">{LOG.join("\n")}</pre>
              </ScrollArea>
            </TabsContent>
          </Tabs>
          <div className="flex flex-wrap items-center gap-2 text-ui-small text-muted-foreground">
            <Kbd>Ctrl+K</Kbd> <Kbd>Ctrl+Enter</Kbd> <Kbd>Alt+↓</Kbd> <Kbd>Esc</Kbd>
          </div>
        </Block>

        <Block title="Overlays">
          <div className="flex flex-wrap items-center gap-2">
            <Dialog>
              <DialogTrigger asChild>
                <Button size="sm" variant="secondary">Dialog</Button>
              </DialogTrigger>
              <DialogContent closeLabel={common("close")}>
                <DialogHeader>
                  <DialogTitle>{t("job.editTranslation")}</DialogTitle>
                  <DialogDescription>{t("review.editDesc")}</DialogDescription>
                </DialogHeader>
                <Textarea aria-label="line" defaultValue="Darum kommt die letzte Zeile so pünktlich wie die erste." />
                <DialogFooter>
                  <DialogClose asChild>
                    <Button size="sm" variant="secondary">{common("cancel")}</Button>
                  </DialogClose>
                  <DialogClose asChild>
                    <Button size="sm">{t("review.save")}</Button>
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button size="sm" variant="secondary">Alert dialog</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t("settings.danger.title")}</AlertDialogTitle>
                  <AlertDialogDescription>{t("settings.danger.confirm")}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{common("cancel")}</AlertDialogCancel>
                  <AlertDialogAction destructive>{t("settings.danger.reset")}</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon-sm" variant="outline" aria-label={common("moreActions")}>
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem>
                  <Play /> {t("voices.listen")}
                  <DropdownMenuShortcut>Alt+P</DropdownMenuShortcut>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Download /> {t("job.download")}
                </DropdownMenuItem>
                <DropdownMenuItem disabled>
                  <FolderOpen /> Show in folder
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuLabel>{common("themeLabel")}</DropdownMenuLabel>
                <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
                  <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem destructive>
                  <Trash2 /> {t("voices.delete")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Popover>
              <PopoverTrigger asChild>
                <Button size="sm" variant="secondary">Popover</Button>
              </PopoverTrigger>
              <PopoverContent>
                <p className="text-ui-section">{t("review.voices")}</p>
                <p className="mt-1 text-ui-small text-muted-foreground">{t("review.voicesHint")}</p>
              </PopoverContent>
            </Popover>
          </div>

          <ContextMenu>
            <ContextMenuTrigger className="flex h-20 items-center justify-center rounded-md border border-dashed border-border-strong text-ui-small text-muted-foreground">
              Right-click here
            </ContextMenuTrigger>
            <ContextMenuContent>
              <ContextMenuItem>
                <Play /> {t("voices.listen")}
                <ContextMenuShortcut>Alt+P</ContextMenuShortcut>
              </ContextMenuItem>
              <ContextMenuItem>
                <Copy /> {common("copy")}
                <ContextMenuShortcut>Ctrl+C</ContextMenuShortcut>
              </ContextMenuItem>
              <ContextMenuSeparator />
              <ContextMenuItem destructive>
                <Trash2 /> {t("voices.delete")}
              </ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        </Block>

        <Block title="Disclosure & loading">
          <Collapsible className="rounded-md border border-border">
            <CollapsibleTrigger className="flex w-full items-center justify-between px-3 py-2 text-left text-ui-body font-medium data-[state=open]:border-b data-[state=open]:border-border">
              {t("settings.advanced.title")}
              <span className="text-ui-small font-normal text-muted-foreground">Whisper: turbo · …</span>
            </CollapsibleTrigger>
            <CollapsibleContent className="px-3 py-2 text-ui-small text-muted-foreground">
              {t("settings.advanced.desc")}
            </CollapsibleContent>
          </Collapsible>
          <div className="space-y-2" aria-label={common("loading")}>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-16 w-full" />
          </div>
        </Block>
      </div>
    </TooltipProvider>
  );
}
