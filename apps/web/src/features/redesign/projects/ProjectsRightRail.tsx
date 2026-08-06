"use client";

import { AlertTriangle, CalendarRange, FileText, Plus, Sparkles, Users } from "lucide-react";
import { AlertRow, RadarStat, SampleTag } from "@/features/redesign/components";
import { ALERTS, RADAR } from "./data";

const QUICK_ACTIONS = [
  { icon: Plus, label: "New Project" },
  { icon: Sparkles, label: "AI Project Plan" },
  { icon: Users, label: "Resource Allocation" },
  { icon: FileText, label: "Project Report" },
  { icon: AlertTriangle, label: "Risk Assessment" },
  { icon: CalendarRange, label: "Project Timeline" },
];

export function ProjectsRightRail() {
  return (
    <div className="space-y-4">
      {/* Project Insights radar */}
      <div className="glow-card p-4">
        <div className="mb-1 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Project Insights</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <RadarStat data={RADAR} height={230} />
        <div className="mt-1 flex items-center justify-center gap-4 text-xs">
          <span className="flex items-center gap-1.5 text-rd-body">
            <span className="h-2 w-2 rounded-full bg-rd-cyan" aria-hidden />
            Your Projects
          </span>
          <span className="flex items-center gap-1.5 text-rd-muted">
            <span className="h-0.5 w-3 border-t border-dashed border-rd-muted" aria-hidden />
            Industry Avg.
          </span>
        </div>
      </div>

      {/* Critical Alerts */}
      <div className="glow-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Critical Alerts</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <div>
          {ALERTS.map((a) => (
            <AlertRow key={a.title} severity={a.severity} title={a.title} />
          ))}
        </div>
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
