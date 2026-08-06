"use client";

import * as React from "react";
import { cn } from "@/lib/cn";

/** Demo mode hides sample-data chips for a clean presentation. Default ON.
 *  When OFF, each section header shows ONE small "sample data" chip. */
const DemoModeContext = React.createContext(true);

export function DemoModeProvider({
  value,
  children,
}: {
  value: boolean;
  children: React.ReactNode;
}) {
  return <DemoModeContext.Provider value={value}>{children}</DemoModeContext.Provider>;
}

export function useDemoMode(): boolean {
  return React.useContext(DemoModeContext);
}

/** One-per-section chip; renders only when demo mode is OFF. */
export function SectionSampleChip({ className }: { className?: string }) {
  const demo = useDemoMode();
  if (demo) return null;
  return (
    <span
      className={cn(
        "inline-flex select-none items-center rounded-full border border-rd-border bg-rd-panel",
        "px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rd-muted",
        className,
      )}
    >
      sample data
    </span>
  );
}

/** Header switch that controls demo mode. */
export function DemoToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label="Demo mode — hide sample-data chips"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-card px-3 py-2 text-sm text-rd-body transition-colors hover:border-rd-border-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
    >
      <span className="text-rd-body">Demo mode</span>
      <span
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors",
          checked ? "bg-rd-grad" : "bg-rd-panel",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-[left]",
            checked ? "left-[18px]" : "left-0.5",
          )}
        />
      </span>
    </button>
  );
}
