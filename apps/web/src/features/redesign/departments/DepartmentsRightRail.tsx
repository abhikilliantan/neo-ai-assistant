"use client";

import {
  BarChart3,
  FileText,
  GitCompare,
  Plus,
  Sparkles,
  Star,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { Donut, SampleTag } from "@/features/redesign/components";
import { AT_RISK, INSIGHTS, OVERVIEW, STATUS_PILL } from "./data";

const QUICK_ACTIONS = [
  { icon: Plus, label: "Add Department" },
  { icon: FileText, label: "Department Report" },
  { icon: Users, label: "Resource Allocation" },
  { icon: GitCompare, label: "Compare Departments" },
  { icon: Star, label: "Performance Review" },
  { icon: BarChart3, label: "Department Analytics" },
];

const INSIGHT_ICONS = [TrendingUp, BarChart3, Sparkles, Users];

export function DepartmentsRightRail() {
  return (
    <div className="space-y-4">
      {/* Department Overview donut */}
      <div className="glow-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Department Overview</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <div className="flex items-center gap-4">
          <Donut
            data={OVERVIEW.buckets.map((b) => ({ label: b.label, value: b.count, color: b.color }))}
            centerValue={OVERVIEW.total}
            centerLabel="Total Departments"
            size={128}
            className="shrink-0"
          />
          <ul className="min-w-0 flex-1 space-y-2">
            {OVERVIEW.buckets.map((b) => (
              <li key={b.label} className="flex items-center gap-2 text-xs">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: b.color }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate text-rd-body">
                  {b.label} ({b.count})
                </span>
                <span className="shrink-0 tabular-nums text-rd-muted">{b.pct}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Department Insights */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Department Insights</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <ul className="space-y-3">
          {INSIGHTS.map((text, i) => {
            const Icon = INSIGHT_ICONS[i % INSIGHT_ICONS.length];
            return (
              <li key={text} className="flex items-start gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                </span>
                <p className="text-sm text-rd-body">{text}</p>
              </li>
            );
          })}
        </ul>
      </div>

      {/* At Risk Departments */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">At Risk Departments</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <ul className="space-y-3">
          {AT_RISK.map((d) => (
            <li key={d.name} className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-rd-heading">{d.name}</p>
                <p className="text-xs text-rd-muted">Performance: {d.performance}%</p>
                <p className="text-xs text-rd-rose">{d.note}</p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium",
                  STATUS_PILL[d.pill],
                )}
              >
                {d.pill}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Quick Actions */}
      <div className="glow-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-rd-heading">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a.label}
              type="button"
              className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
            >
              <a.icon className="h-4 w-4 shrink-0 text-rd-cyan" aria-hidden />
              <span className="truncate">{a.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
