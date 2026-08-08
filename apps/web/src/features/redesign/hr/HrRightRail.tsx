"use client";

import {
  BriefcaseBusiness,
  CalendarDays,
  ClipboardCheck,
  FileText,
  MessagesSquare,
  Plus,
  TriangleAlert,
  UserPlus,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AvatarStack, QuickActionButton, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { AI_RECS, OPEN_ROLES, QUICK_ACTIONS, UPCOMING } from "./data";

const UP_ICON: Record<string, LucideIcon> = {
  interview: CalendarDays,
  review: ClipboardCheck,
  onboard: UserPlus,
  oneonone: MessagesSquare,
};
const QA_ICON: Record<string, LucideIcon> = {
  add: UserPlus,
  post: BriefcaseBusiness,
  payroll: Wallet,
  report: FileText,
};
const REC_TONE: Record<string, string> = {
  rose: "text-rd-rose",
  amber: "text-rd-amber",
  cyan: "text-rd-cyan",
};
const PRIORITY: Record<string, string> = {
  High: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  Medium: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  Low: "border-rd-border bg-rd-panel text-rd-muted",
};

export function HrRightRail() {
  return (
    <div className="space-y-4">
      {/* Upcoming */}
      <div className="glow-card p-4">
        <Head title="Upcoming" />
        <ul className="space-y-3">
          {UPCOMING.map((a) => {
            const Icon = UP_ICON[a.icon];
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

      {/* Open Positions */}
      <div className="glow-card p-4">
        <Head title="Open Positions" />
        <ul className="space-y-3">
          {OPEN_ROLES.map((o, i) => (
            <li key={o.role} className="flex items-center gap-3">
              <span className="w-4 shrink-0 text-sm font-semibold text-rd-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{o.role}</p>
                <p className="truncate text-xs text-rd-muted">{o.dept}</p>
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
        <div className="mb-3 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">Quick Actions</h3>
          <Plus className="h-4 w-4 text-rd-muted" aria-hidden />
        </div>
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
