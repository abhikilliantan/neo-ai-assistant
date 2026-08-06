"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  CalendarClock,
  FileText,
  ListChecks,
  MessageSquare,
  Plus,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { AlertRow, SectionSampleChip } from "@/features/redesign/components";
import { navHref } from "@/features/redesign/shell";
import { ALERTS, MEETINGS, RECOMMENDATIONS } from "./data";

type Tone = "cyan" | "green" | "rose" | "neutral";

const ACTION_TONE: Record<Tone, string> = {
  cyan: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan hover:bg-rd-cyan/20",
  green: "border-rd-green/40 bg-rd-green/10 text-rd-green hover:bg-rd-green/20",
  rose: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose hover:bg-rd-rose/20",
  neutral:
    "border-rd-border bg-rd-card text-rd-body hover:border-rd-border-hover hover:text-rd-heading",
};

const ACTIONS: { icon: LucideIcon; label: string; href: Route; tone: Tone }[] = [
  { icon: MessageSquare, label: "Launch AI Chat", href: navHref("ai-chat"), tone: "cyan" },
  { icon: FileText, label: "Generate Report", href: navHref("reports"), tone: "neutral" },
  { icon: ShieldAlert, label: "Approve Purchase", href: navHref("finance"), tone: "green" },
  { icon: ListChecks, label: "View Risks", href: navHref("analytics"), tone: "rose" },
  { icon: CalendarClock, label: "Create Meeting", href: navHref("meetings"), tone: "cyan" },
  { icon: Plus, label: "Add Task", href: navHref("projects"), tone: "neutral" },
];

export function ExecRightRail() {
  const router = useRouter();

  return (
    <div className="space-y-4">
      {/* Upcoming Meetings */}
      <RailCard title="Upcoming Meetings" sample>
        <ul className="space-y-3">
          {MEETINGS.map((m) => (
            <li key={m.title} className="flex items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-rd-border bg-rd-panel text-rd-cyan">
                <CalendarClock className="h-4 w-4" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-rd-heading">{m.title}</span>
                <span className="block truncate text-xs text-rd-muted">{m.time}</span>
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold",
                  m.now ? "bg-rd-green/15 text-rd-green" : "border border-rd-border text-rd-muted",
                )}
              >
                {m.badge}
              </span>
            </li>
          ))}
        </ul>
      </RailCard>

      {/* Critical Alerts */}
      <RailCard title="Critical Alerts" sample>
        <div>
          {ALERTS.map((a) => (
            <AlertRow key={a.title} severity={a.severity} title={a.title} meta={a.meta} />
          ))}
        </div>
      </RailCard>

      {/* AI Recommendations */}
      <RailCard title="AI Recommendations" sample>
        <ul className="space-y-3">
          {RECOMMENDATIONS.map((r) => (
            <li key={r.title} className="flex items-start gap-2.5">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-rd-violet" aria-hidden />
              <span className="min-w-0">
                <span className="block text-sm text-rd-heading">{r.title}</span>
                <span className="block text-xs text-rd-muted">{r.sub}</span>
              </span>
            </li>
          ))}
        </ul>
      </RailCard>

      {/* Quick Actions — real navigation */}
      <RailCard title="Quick Actions">
        <div className="grid grid-cols-2 gap-2.5">
          {ACTIONS.map((a) => {
            const Icon = a.icon;
            return (
              <button
                key={a.label}
                type="button"
                onClick={() => router.push(a.href)}
                className={cn(
                  "flex items-center gap-2 rounded-control border px-3 py-2 text-xs font-medium transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60",
                  ACTION_TONE[a.tone],
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className="truncate">{a.label}</span>
              </button>
            );
          })}
        </div>
      </RailCard>
    </div>
  );
}

function RailCard({
  title,
  sample,
  children,
}: {
  title: string;
  sample?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="glow-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-rd-heading">{title}</h3>
        {sample && <SectionSampleChip />}
      </div>
      {children}
    </div>
  );
}
