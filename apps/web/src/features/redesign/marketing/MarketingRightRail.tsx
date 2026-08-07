"use client";

import {
  CalendarDays,
  FileEdit,
  FilePlus2,
  FileText,
  Linkedin,
  Lightbulb,
  Mail,
  Megaphone,
  Youtube,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { QuickActionButton, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { ACTIVITIES, AI_RECS, QUICK_ACTIONS, TASKS } from "./data";

const ACT_ICON: Record<string, LucideIcon> = {
  blog: FileText,
  linkedin: Linkedin,
  email: Mail,
  youtube: Youtube,
  ad: Megaphone,
};
const QA_ICON: Record<string, LucideIcon> = {
  campaign: FilePlus2,
  content: FileEdit,
  report: FileText,
  calendar: CalendarDays,
};
const REC_TONE: Record<string, string> = {
  rose: "text-rd-rose",
  amber: "text-rd-amber",
  green: "text-rd-green",
  cyan: "text-rd-cyan",
};
const PRIORITY: Record<string, string> = {
  High: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  Medium: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  Low: "border-rd-border bg-rd-panel text-rd-muted",
};

export function MarketingRightRail() {
  return (
    <div className="space-y-4">
      {/* Marketing Activities */}
      <div className="glow-card p-4">
        <Head title="Marketing Activities" />
        <ul className="space-y-3">
          {ACTIVITIES.map((a) => {
            const Icon = ACT_ICON[a.icon];
            return (
              <li key={a.title} className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-rd-heading">{a.title}</p>
                  <p className="truncate text-xs text-rd-muted">{a.sub}</p>
                </div>
                <span className="shrink-0 text-xs text-rd-muted">{a.when}</span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Marketing Tasks */}
      <div className="glow-card p-4">
        <Head title="Marketing Tasks" />
        <ul className="space-y-2.5">
          {TASKS.map((t) => (
            <li key={t.label} className="flex items-center gap-2.5">
              <span
                className="h-4 w-4 shrink-0 rounded border border-rd-border bg-rd-panel"
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-sm text-rd-body">{t.label}</span>
              <span className="shrink-0 text-[11px] text-rd-muted">{t.due}</span>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium",
                  PRIORITY[t.priority],
                )}
              >
                {t.priority}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* AI Recommendations */}
      <div className="glow-card p-4">
        <Head title="AI Recommendations" />
        <ul className="space-y-3">
          {AI_RECS.map((r) => (
            <li key={r.text} className="flex items-start gap-2.5">
              <Lightbulb className={cn("mt-0.5 h-4 w-4 shrink-0", REC_TONE[r.tone])} aria-hidden />
              <p className="text-sm text-rd-body">{r.text}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* Quick Actions */}
      <div className="glow-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-rd-heading">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {QUICK_ACTIONS.map((a) => (
            <QuickActionButton key={a.label} icon={QA_ICON[a.icon]} label={a.label} />
          ))}
        </div>
      </div>
    </div>
  );
}

function Head({ title }: { title: string }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      <span className="text-xs font-medium text-rd-cyan">View all</span>
    </div>
  );
}
