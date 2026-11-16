"use client";

import * as React from "react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  menuContent,
  menuItem,
  menuItemDestructive,
  menuLabel,
  menuSeparator,
  menuShortcut,
} from "./menu-styles";

const DropdownMenu = Menu.Root;
const DropdownMenuTrigger = Menu.Trigger;
const DropdownMenuGroup = Menu.Group;
const DropdownMenuRadioGroup = Menu.RadioGroup;

function DropdownMenuContent({
  className,
  sideOffset = 6,
  align = "end",
  ...props
}: React.ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(menuContent, className)}
        {...props}
      />
    </Menu.Portal>
  );
}

function DropdownMenuItem({
  className,
  destructive,
  ...props
}: React.ComponentProps<typeof Menu.Item> & { destructive?: boolean }) {
  return (
    <Menu.Item className={cn(menuItem, destructive && menuItemDestructive, className)} {...props} />
  );
}

function DropdownMenuCheckboxItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Menu.CheckboxItem>) {
  return (
    <Menu.CheckboxItem className={cn(menuItem, "pl-8", className)} {...props}>
      <span className="absolute left-2 flex size-4 items-center justify-center">
        <Menu.ItemIndicator>
          <Check className="text-foreground" />
        </Menu.ItemIndicator>
      </span>
      {children}
    </Menu.CheckboxItem>
  );
}

function DropdownMenuRadioItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Menu.RadioItem>) {
  return (
    <Menu.RadioItem className={cn(menuItem, "pl-8", className)} {...props}>
      <span className="absolute left-2 flex size-4 items-center justify-center">
        <Menu.ItemIndicator>
          <Circle className="size-2 fill-current text-primary" />
        </Menu.ItemIndicator>
      </span>
      {children}
    </Menu.RadioItem>
  );
}

function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof Menu.Label>) {
  return <Menu.Label className={cn(menuLabel, className)} {...props} />;
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Menu.Separator>) {
  return <Menu.Separator className={cn(menuSeparator, className)} {...props} />;
}

/** A keyboard shortcut shown at an item's end (it doesn't bind the key). */
function DropdownMenuShortcut({ className, ...props }: React.ComponentProps<"span">) {
  return <span className={cn(menuShortcut, className)} {...props} />;
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
};
