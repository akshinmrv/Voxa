"use client";

import * as React from "react";
import * as Menu from "@radix-ui/react-context-menu";
import { cn } from "@/lib/utils";
import {
  menuContent,
  menuItem,
  menuItemDestructive,
  menuLabel,
  menuSeparator,
  menuShortcut,
} from "./menu-styles";

// Voxa Studio's window turns off WebView2's own right-click menu, so the console gives the
// places that need one its own (VOXA_DESIGN_PLAN.md §7.7).
// Not modal, as the dropdown menus aren't (components/ui/dropdown-menu.tsx).
function ContextMenu({ modal = false, ...props }: React.ComponentProps<typeof Menu.Root>) {
  return <Menu.Root modal={modal} {...props} />;
}
const ContextMenuTrigger = Menu.Trigger;
const ContextMenuGroup = Menu.Group;

function ContextMenuContent({ className, ...props }: React.ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content className={cn(menuContent, className)} {...props} />
    </Menu.Portal>
  );
}

function ContextMenuItem({
  className,
  destructive,
  ...props
}: React.ComponentProps<typeof Menu.Item> & { destructive?: boolean }) {
  return (
    <Menu.Item className={cn(menuItem, destructive && menuItemDestructive, className)} {...props} />
  );
}

function ContextMenuLabel({ className, ...props }: React.ComponentProps<typeof Menu.Label>) {
  return <Menu.Label className={cn(menuLabel, className)} {...props} />;
}

function ContextMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Menu.Separator>) {
  return <Menu.Separator className={cn(menuSeparator, className)} {...props} />;
}

function ContextMenuShortcut({ className, ...props }: React.ComponentProps<"span">) {
  return <span className={cn(menuShortcut, className)} {...props} />;
}

export {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuGroup,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
};
