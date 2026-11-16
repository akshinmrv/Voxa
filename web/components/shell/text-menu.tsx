"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ClipboardPaste, Copy, Scissors, TextSelect } from "lucide-react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { keyLabel } from "@/lib/shortcuts";

type Field = HTMLInputElement | HTMLTextAreaElement;

function fieldOf(target: EventTarget | null): Field | null {
  if (target instanceof HTMLTextAreaElement) return target;
  if (target instanceof HTMLInputElement && /^(text|search|url|email|number|password|)$/.test(target.type))
    return target;
  return null;
}

type Aim = { field: Field | null; start: number; end: number; selected: string };

/**
 * Voxa Studio's window has no right-click menu of its own (WebView2's is off outside debug
 * builds), so text fields had no Cut, Copy or Paste by mouse. In the window — only there; a
 * browser has its own — a right-click on a field, or on selected text, gets this one. A
 * right-click menu of a component's own (a line's, later) opens instead of it.
 */
export function TextMenu({ enabled, children }: { enabled: boolean; children: React.ReactNode }) {
  const t = useTranslations("App.shell.edit");
  const aim = useRef<Aim>({ field: null, start: 0, end: 0, selected: "" });
  const [can, setCan] = useState({ cut: false, copy: false, paste: false, all: false });

  function onContextMenu(event: React.MouseEvent) {
    const field = fieldOf(event.target);
    const selected = field
      ? field.value.slice(field.selectionStart ?? 0, field.selectionEnd ?? 0)
      : (window.getSelection()?.toString() ?? "");
    if (!field && !selected) {
      event.preventDefault(); // nothing to edit or copy here: no menu
      return;
    }
    aim.current = {
      field,
      start: field?.selectionStart ?? 0,
      end: field?.selectionEnd ?? 0,
      selected,
    };
    const writable = !!field && !field.readOnly && !field.disabled;
    setCan({ cut: writable && !!selected, copy: !!selected, paste: writable, all: !!field });
  }

  /** Back into the field, with the selection it had when the menu opened. */
  function refocus(): Field | null {
    const { field, start, end } = aim.current;
    if (!field) return null;
    field.focus();
    field.setSelectionRange(start, end);
    return field;
  }

  async function copy() {
    await navigator.clipboard.writeText(aim.current.selected).catch(() => {});
    refocus();
  }

  async function cut() {
    await navigator.clipboard.writeText(aim.current.selected).catch(() => {});
    // insertText keeps it on the field's undo stack, and tells React the value changed.
    if (refocus()) document.execCommand("insertText", false, "");
  }

  async function paste() {
    const text = await navigator.clipboard.readText().catch(() => null);
    if (refocus() && text) document.execCommand("insertText", false, text);
  }

  function selectAll() {
    refocus()?.select();
  }

  return (
    <ContextMenu modal={false}>
      <ContextMenuTrigger asChild disabled={!enabled} onContextMenu={onContextMenu}>
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </ContextMenuTrigger>
      <ContextMenuContent onCloseAutoFocus={(event) => event.preventDefault()}>
        <ContextMenuItem disabled={!can.cut} onSelect={() => void cut()}>
          <Scissors /> {t("cut")}
          <ContextMenuShortcut>{keyLabel(["Mod", "X"])}</ContextMenuShortcut>
        </ContextMenuItem>
        <ContextMenuItem disabled={!can.copy} onSelect={() => void copy()}>
          <Copy /> {t("copy")}
          <ContextMenuShortcut>{keyLabel(["Mod", "C"])}</ContextMenuShortcut>
        </ContextMenuItem>
        <ContextMenuItem disabled={!can.paste} onSelect={() => void paste()}>
          <ClipboardPaste /> {t("paste")}
          <ContextMenuShortcut>{keyLabel(["Mod", "V"])}</ContextMenuShortcut>
        </ContextMenuItem>
        <ContextMenuItem disabled={!can.all} onSelect={selectAll}>
          <TextSelect /> {t("selectAll")}
          <ContextMenuShortcut>{keyLabel(["Mod", "A"])}</ContextMenuShortcut>
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
