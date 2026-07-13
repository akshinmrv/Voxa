"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { TerminalBlock } from "@/components/patterns/terminal-block";
import { SectionHeader } from "./section-header";
import { cn } from "@/lib/utils";

type Tab = { name: string; label: string; command: string };

export function QuickStart() {
  const t = useTranslations("QuickStart");
  const tabs = t.raw("tabs") as Tab[];
  const [active, setActive] = useState(0);

  return (
    <section className="scroll-mt-20">
      <div className="mx-auto w-full max-w-3xl px-6 py-24">
        <SectionHeader
          label={t("label")}
          title={t("title")}
          subtitle={t("subtitle")}
        />
        <div className="mt-12">
          <div
            role="tablist"
            aria-label={t("title")}
            className="flex flex-wrap gap-2"
          >
            {tabs.map((tab, i) => (
              <button
                key={tab.name}
                role="tab"
                type="button"
                aria-selected={i === active}
                onClick={() => setActive(i)}
                className={cn(
                  "rounded-sm border px-3 py-1.5 text-sm font-medium transition-colors",
                  i === active
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border bg-surface-1 text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.name}
              </button>
            ))}
          </div>
          <div className="mt-4">
            <TerminalBlock
              label={tabs[active].label}
              command={tabs[active].command}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
