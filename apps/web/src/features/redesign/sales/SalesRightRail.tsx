"use client";

import {
  BarChart3,
  CalendarDays,
  ClipboardList,
  FileSignature,
  FileText,
  Phone,
  Plus,
  TriangleAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AvatarStack, QuickActionButton, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { ACTIVITIES, AI_RECS, OPPORTUNITIES, QUICK_ACTIONS } from "./data";

const ACT_ICON: Record<string, LucideIcon> = {
  demo: CalendarDays,
  proposal: FileText,
  contract: FileSignature,
  discovery: Phone,
};
const QA_ICON: Record<string, LucideIcon> = {
  add: Plus,
  log: ClipboardList,
  report: FileText,
  forecast: BarChart3,
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

export function SalesRightRail() {
  return (
    <div className="space-y-4">
      {/* Sales Activities */}
      <div className="glow-card p-4">
        <Head title="Sales Activities" />
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
                  <p className="truncate text-xs text-rd-muted">{a.when}</p>
                </div>
                <AvatarStack names={a.people} extra={a.extra} size={22} />
              </li>
            );
          })}
        </ul>
      </div>

      {/* Top Opportunities */}
      <div className="glow-card p-4">
        <Head title="Top Opportunities" />
        <ul className="space-y-3">
          {OPPORTUNITIES.map((o, i) => (
            <li key={o.name} className="flex items-center gap-3">
              <span className="w-4 shrink-0 text-sm font-semibold text-rd-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{o.name}</p>
                <p className="truncate text-xs text-rd-muted">
                  {o.value} • {o.stage}
                </p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                  PRIORITY[o.priority],
                )}
              >
                {o.priority}
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
              <TriangleAlert
                className={cn("mt-0.5 h-4 w-4 shrink-0", REC_TONE[r.tone])}
                aria-hidden
              />
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
