"use client";

import { createContext, useContext } from "react";

/** What any part of the shell can open: the command palette and the shortcuts list. */
export type ShellActions = {
  openPalette: () => void;
  openShortcuts: () => void;
};

export const ShellContext = createContext<ShellActions>({
  openPalette: () => {},
  openShortcuts: () => {},
});

export const useShell = () => useContext(ShellContext);
