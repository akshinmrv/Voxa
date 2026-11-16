// Shared look of the dropdown and context menus (and the command palette later), so a
// right-click menu and a ⋯ menu can't drift apart.
export const menuContent =
  "z-50 min-w-44 overflow-hidden rounded-md border border-border bg-surface-3 p-1 text-ui-body text-foreground shadow-overlay data-[state=open]:animate-voxa-in data-[state=closed]:animate-voxa-out";

export const menuItem =
  "relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 outline-none transition-colors duration-(--dur-1) data-[highlighted]:bg-surface-2 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-muted-foreground";

export const menuItemDestructive =
  "text-danger data-[highlighted]:bg-danger/10 [&_svg]:text-danger";

export const menuSeparator = "-mx-1 my-1 h-px bg-border";

export const menuLabel = "px-2 py-1.5 text-ui-label uppercase text-muted-foreground";

export const menuShortcut = "ml-auto pl-6 font-mono text-ui-mono text-fg-subtle";
