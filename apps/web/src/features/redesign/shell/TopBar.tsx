"use client";

import {
  Bell,
  CalendarClock,
  ChevronDown,
  HelpCircle,
  PanelLeft,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/cn";

interface TopBarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const QUICK_QUESTIONS = [
  "Bidco project status?",
  "Projects delayed?",
  "Cash position?",
  "Employees needing attention?",
];

export function TopBar({ collapsed, onToggle }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-rd-border bg-rd-panel/80 backdrop-blur-xl">
      <div className="flex items-center gap-4 px-4 py-3 sm:px-6">
        {/* Left */}
        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={collapsed}
            className="rounded-control p-2 text-rd-body transition-colors hover:bg-rd-card hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
          >
            <PanelLeft className="h-[18px] w-[18px]" />
          </button>
          <span className="hidden items-center gap-2 rounded-full border border-rd-green/40 bg-rd-green/10 px-3 py-1 text-xs font-medium text-rd-green md:inline-flex">
            <span className="h-1.5 w-1.5 rounded-full bg-rd-green" aria-hidden />
            All Systems Operational
          </span>
        </div>

        {/* Center: search */}
        <div className="mx-auto w-full max-w-xl">
          <label className="relative block">
            <span className="sr-only">Ask NEO anything</span>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-rd-muted"
              aria-hidden
            />
            <input
              type="search"
              placeholder="Ask NEO anything…"
              className="h-10 w-full rounded-control border border-rd-border bg-rd-card pl-9 pr-16 text-sm text-rd-heading placeholder:text-rd-muted focus-visible:border-rd-border-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/40"
            />
            <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-rd-border bg-rd-panel px-1.5 py-0.5 text-[10px] font-medium text-rd-muted sm:inline-flex">
              ⌘K
            </kbd>
          </label>
        </div>

        {/* Right */}
        <div className="flex shrink-0 items-center gap-1.5">
          <IconBadge icon={Bell} label="AI Alerts" count={12} />
          <IconBadge icon={CalendarClock} label="Meetings" count={6} />
          <IconButton icon={HelpCircle} label="Help" />
          <IconButton icon={Settings} label="Settings" />
          <button
            type="button"
            className="ml-1 flex items-center gap-2 rounded-control border border-rd-border bg-rd-card py-1 pl-1 pr-2 text-left transition-colors hover:border-rd-border-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
            aria-label="Account menu — Abhishek, CEO"
          >
            <span className="gradient-ring relative flex h-7 w-7 items-center justify-center rounded-full bg-rd-panel text-xs font-semibold text-rd-heading">
              A
            </span>
            <span className="hidden leading-tight lg:block">
              <span className="block text-xs font-medium text-rd-heading">Abhishek</span>
              <span className="block text-[10px] text-rd-muted">CEO</span>
            </span>
            <ChevronDown className="hidden h-4 w-4 text-rd-muted lg:block" aria-hidden />
          </button>
        </div>
      </div>

      {/* Quick-question chips */}
      <div className="flex flex-wrap items-center gap-2 px-4 pb-3 sm:px-6">
        <span className="text-[11px] text-rd-muted">Try:</span>
        {QUICK_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="rounded-full border border-rd-border bg-rd-card px-3 py-1 text-xs text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
          >
            {q}
          </button>
        ))}
      </div>
    </header>
  );
}

function IconButton({ icon: Icon, label }: { icon: typeof Bell; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="rounded-control p-2 text-rd-body transition-colors hover:bg-rd-card hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
    >
      <Icon className="h-[18px] w-[18px]" />
    </button>
  );
}

function IconBadge({
  icon: Icon,
  label,
  count,
}: {
  icon: typeof Bell;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      aria-label={`${label} (${count})`}
      className="relative rounded-control p-2 text-rd-body transition-colors hover:bg-rd-card hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
    >
      <Icon className="h-[18px] w-[18px]" />
      <span
        className={cn(
          "absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full",
          "bg-rd-rose px-1 text-[10px] font-semibold tabular-nums text-white",
        )}
      >
        {count}
      </span>
    </button>
  );
}
