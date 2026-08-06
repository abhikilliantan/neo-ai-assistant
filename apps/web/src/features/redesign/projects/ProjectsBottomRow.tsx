"use client";

import { BarChart3, FileCheck2, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Donut, GanttTimeline, SampleTag } from "@/features/redesign/components";
import { PREDICTIONS, RESOURCES, TIMELINE_MONTHS, TIMELINE_ROWS } from "./data";

const LEGEND: { label: string; cls: string }[] = [
  { label: "On Track", cls: "bg-rd-green" },
  { label: "At Risk", cls: "bg-rd-amber" },
  { label: "Delayed", cls: "bg-rd-rose" },
  { label: "Completed", cls: "bg-rd-cyan" },
];

const PRED_ICONS: LucideIcon[] = [TrendingUp, BarChart3, FileCheck2];

export function ProjectsBottomRow() {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1.1fr)_minmax(0,1fr)]">
      {/* Timeline */}
      <div className="glow-card p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Project Timeline Overview</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View full timeline</span>
        </div>
        <GanttTimeline months={TIMELINE_MONTHS} rows={TIMELINE_ROWS} labelWidth={168} />
        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-rd-border pt-3">
          {LEGEND.map((l) => (
            <span key={l.label} className="flex items-center gap-1.5 text-xs text-rd-body">
              <span className={`h-2 w-2 rounded-full ${l.cls}`} aria-hidden />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      {/* Resource allocation */}
      <div className="glow-card p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Resource Allocation</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View details</span>
        </div>
        <div className="flex items-center gap-4">
          <Donut
            data={RESOURCES.slices}
            centerValue={RESOURCES.total}
            centerLabel="Total Resources"
            size={150}
            className="shrink-0"
          />
          <ul className="min-w-0 flex-1 space-y-2.5">
            {RESOURCES.slices.map((s) => (
              <li key={s.label} className="flex items-center gap-2 text-sm">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: s.color }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
                <span className="shrink-0 tabular-nums text-rd-heading">{s.value}</span>
                <span className="shrink-0 text-xs text-rd-muted">({s.pct})</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* AI predictions */}
      <div className="glow-card p-5">
        <div className="mb-4 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">AI Project Predictions</h3>
          <SampleTag />
        </div>
        <ul className="space-y-3">
          {PREDICTIONS.map((p, i) => {
            const Icon = PRED_ICONS[i % PRED_ICONS.length];
            return (
              <li key={p} className="flex items-start gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                </span>
                <p className="text-sm text-rd-body">{p}</p>
              </li>
            );
          })}
        </ul>
        <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-rd-cyan">
          View all predictions →
        </span>
      </div>
    </div>
  );
}
