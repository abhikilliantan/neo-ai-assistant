"use client";

import {
  BarChart3,
  Building2,
  CalendarClock,
  FileText,
  Landmark,
  Plus,
  Receipt,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { QuickActionButton, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { AI_RECS, PAYMENTS, QUICK_ACTIONS, TOP_EXPENSES } from "./data";

const PAY_ICON: Record<string, LucideIcon> = {
  invoice: FileText,
  payroll: Wallet,
  tax: Landmark,
  vendor: Building2,
};
const QA_ICON: Record<string, LucideIcon> = {
  invoice: Plus,
  expense: Receipt,
  report: FileText,
  forecast: BarChart3,
};
const REC_TONE: Record<string, string> = {
  rose: "text-rd-rose",
  amber: "text-rd-amber",
  cyan: "text-rd-cyan",
};
const CATEGORY: Record<string, string> = {
  Payroll: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
  Operations: "border-rd-violet/40 bg-rd-violet/10 text-rd-violet",
  Marketing: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
  "R&D": "border-rd-violet/40 bg-rd-violet/10 text-rd-violet",
};

export function FinanceRightRail() {
  return (
    <div className="space-y-4">
      {/* Upcoming Payments */}
      <div className="glow-card p-4">
        <Head title="Upcoming Payments" />
        <ul className="space-y-3">
          {PAYMENTS.map((p) => {
            const Icon = PAY_ICON[p.icon];
            return (
              <li key={p.title} className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-rd-heading">{p.title}</p>
                  <p className="truncate text-xs text-rd-muted">{p.when}</p>
                </div>
                <span className="shrink-0 text-sm font-semibold tabular-nums text-rd-heading">
                  {p.amount}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Top Expenses */}
      <div className="glow-card p-4">
        <Head title="Top Expenses" />
        <ul className="space-y-3">
          {TOP_EXPENSES.map((e, i) => (
            <li key={e.name} className="flex items-center gap-3">
              <span className="w-4 shrink-0 text-sm font-semibold text-rd-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{e.name}</p>
                <p className="truncate text-xs text-rd-muted">{e.amount}</p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                  CATEGORY[e.category],
                )}
              >
                {e.category}
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
          <CalendarClock className="h-4 w-4 text-rd-muted" aria-hidden />
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
