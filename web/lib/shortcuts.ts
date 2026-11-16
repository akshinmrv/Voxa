// The console's keyboard shortcuts, in one place: the key handler, the shortcuts list and the
// command palette all read this, so a shortcut can't be shown that doesn't work, or work
// unlisted (VOXA_DESIGN_PLAN.md §6.8).

export type ShortcutId =
  | "palette"
  | "newDub"
  | "settings"
  | "sidebar"
  | "goTo"
  | "help"
  | "close"
  | "openFile"
  | "run"
  | "nextLine"
  | "playLine"
  | "toggleSource"
  | "save";

export type Shortcut = {
  id: ShortcutId;
  /** "Mod" is Ctrl, or ⌘ on a Mac. */
  keys: string[];
  /** A browser keeps these keys for itself (Ctrl+N, Ctrl+1…): Voxa Studio's window only. */
  desktopOnly?: boolean;
};

export const SHORTCUTS: Shortcut[] = [
  { id: "palette", keys: ["Mod", "K"] },
  { id: "newDub", keys: ["Mod", "N"], desktopOnly: true },
  { id: "goTo", keys: ["Mod", "1…4"], desktopOnly: true },
  { id: "settings", keys: ["Mod", ","] },
  { id: "sidebar", keys: ["Mod", "B"] },
  { id: "help", keys: ["?"] },
  { id: "close", keys: ["Esc"] },
  // The Studio page's own (components/studio/composer.tsx handles them).
  { id: "openFile", keys: ["Mod", "O"] },
  { id: "run", keys: ["Mod", "Enter"] },
  // A dub's lines (components/workspace/lines-view.tsx handles them).
  { id: "nextLine", keys: ["Alt", "↑↓"] },
  { id: "playLine", keys: ["Alt", "P"] },
  { id: "toggleSource", keys: ["Alt", "O"] },
  { id: "save", keys: ["Mod", "S"] },
];

export function isMac(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
}

/** A shortcut as the keyboard shows it here: Ctrl+K, or ⌘K on a Mac. */
export function keyLabel(keys: string[], mac = isMac()): string {
  const shown = keys.map((k) => (k === "Mod" ? (mac ? "⌘" : "Ctrl") : k));
  return mac ? shown.join("") : shown.join("+");
}

/** Typing into a field: plain keys (?, Space) are the text's, not shortcuts. */
export function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return true;
  if (target instanceof HTMLInputElement) {
    return !["checkbox", "radio", "button", "submit", "reset", "range", "file", "color"].includes(
      target.type,
    );
  }
  return false;
}
