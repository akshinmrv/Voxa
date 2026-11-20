"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { usePathname, useRouter } from "@/i18n/navigation";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toaster";
import { UpdateBanner } from "@/components/app/update-banner";
import { APP_NAV, SETTINGS_NAV } from "@/components/app/nav-items";
import { useDesktop } from "@/lib/desktop";
import { isTyping } from "@/lib/shortcuts";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { StatusBar } from "./status-bar";
import { CommandPalette } from "./command-palette";
import { ShortcutsDialog } from "./shortcuts-dialog";
import { TextMenu } from "./text-menu";
import { ShellContext } from "./shell-context";
import { toggleSidebar } from "./sidebar-state";

/**
 * The app's frame (VOXA_DESIGN_PLAN.md §6.3): sidebar, header, the page, and the status bar,
 * filling the window. The page scrolls on its own, inside, as a desktop app's does, while
 * the frame stays put.
 */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const desktop = useDesktop();
  const { resolvedTheme } = useTheme();
  const [palette, setPalette] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  const main = useRef<HTMLElement>(null);

  // The keys of §6.8 that work anywhere. A browser keeps Ctrl+N and Ctrl+1… for itself,
  // so those are Voxa Studio's window's only.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const mod = event.ctrlKey || event.metaKey;
      if (mod && !event.altKey && !event.shiftKey) {
        const key = event.key.toLowerCase();
        const nav = desktop && /^[1-4]$/.test(key) ? APP_NAV[Number(key) - 1] : null;
        const go =
          key === "k"
            ? () => setPalette((open) => !open)
            : key === "b"
              ? toggleSidebar
              : key === ","
                ? () => router.push(SETTINGS_NAV.href)
                : desktop && key === "n"
                  ? () => router.push("/app")
                  : nav
                    ? () => router.push(nav.href)
                    : null;
        if (go) {
          event.preventDefault();
          go();
        }
        return;
      }
      if (event.key === "?" && !mod && !event.altKey && !isTyping(event.target)) {
        event.preventDefault();
        setShortcuts(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, desktop]);

  // The window's title bar follows the console's theme (Voxa Studio only).
  useEffect(() => {
    if (desktop && (resolvedTheme === "dark" || resolvedTheme === "light")) {
      desktop.set_chrome(resolvedTheme).catch(() => {});
    }
  }, [desktop, resolvedTheme]);

  // The page scrolls inside the frame, so a new page starts at its own top.
  useEffect(() => {
    main.current?.scrollTo(0, 0);
  }, [pathname]);

  const actions = useMemo(
    () => ({ openPalette: () => setPalette(true), openShortcuts: () => setShortcuts(true) }),
    [],
  );

  return (
    <ShellContext.Provider value={actions}>
      <TooltipProvider>
        <div className="flex h-dvh flex-col overflow-hidden bg-background">
          <div className="flex min-h-0 flex-1">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Header />
              <UpdateBanner />
              <TextMenu enabled={!!desktop}>
                <main
                  id="main-content"
                  ref={main}
                  tabIndex={-1}
                  className="min-h-0 flex-1 overflow-y-auto px-4 py-6 outline-none md:px-8"
                >
                  {children}
                </main>
              </TextMenu>
            </div>
          </div>
          <StatusBar />
        </div>
        <CommandPalette
          open={palette}
          onOpenChange={setPalette}
          onShortcuts={() => setShortcuts(true)}
        />
        <ShortcutsDialog open={shortcuts} onOpenChange={setShortcuts} />
        <Toaster />
      </TooltipProvider>
    </ShellContext.Provider>
  );
}
