"use client";

import * as C from "@radix-ui/react-collapsible";

// Unstyled on purpose: what opens (the composer's "More", a log) styles its own trigger.
// It opens at once rather than by animating its height, which would move the layout.
const Collapsible = C.Root;
const CollapsibleTrigger = C.Trigger;
const CollapsibleContent = C.Content;

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
