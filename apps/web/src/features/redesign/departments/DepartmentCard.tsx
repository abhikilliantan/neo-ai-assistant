"use client";

import { cn } from "@/lib/cn";
import { Delta, SampleTag, Sparkline } from "@/features/redesign/components";
import { RING_COLOR, STATUS_PILL, type MergedDept } from "./data";

export function DepartmentCard({ dept, index }: { dept: MergedDept; index: number }) {
  return (
    <div className="glow-card p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-rd-grad text-sm font-bold text-white">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-rd-heading">{dept.name}</p>
            <p className="truncate text-xs text-rd-muted">{dept.descriptor}</p>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
            STATUS_PILL[dept.status],
          )}
        >
          {dept.status}
        </span>
      </div>

      {/* Body: ring + metrics + sparkline */}
      <div className="mt-4 flex gap-5">
        <div className="flex shrink-0 flex-col items-center gap-1">
          <PerfRing pct={dept.performance} color={RING_COLOR[dept.color]} />
          <span className="flex items-center gap-1 text-xs text-rd-muted">
            Performance
            {!dept.performanceReal && <SampleTag />}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="grid grid-cols-3 gap-3">
            <Metric
              label="Headcount"
              value={`${dept.headcount}`}
              delta={dept.headcountDelta}
              deltaSuffix=""
              sample
            />
            <Metric
              label={dept.middle.label}
              value={dept.middle.value}
              sub={dept.middle.sub}
              delta={dept.middle.delta}
              sample={!dept.projectsReal}
            />
            <Metric label="Budget" value={dept.budget} sub={`${dept.budgetPct}%`} sample />
          </div>
          <Sparkline data={dept.spark} color={dept.color} height={40} className="mt-3" />
        </div>
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-rd-border pt-3 text-xs">
        <span className="truncate text-rd-body">
          Lead: <span className="text-rd-heading">{dept.lead}</span>
        </span>
        <span className="shrink-0 text-rd-muted">Updated {dept.updated} ago</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  delta,
  deltaSuffix = "%",
  sample,
}: {
  label: string;
  value: string;
  sub?: string;
  delta?: number;
  deltaSuffix?: string;
  sample?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="flex items-center gap-1 truncate text-[11px] text-rd-muted">
        {label}
        {sample && <SampleTag />}
      </p>
      <p className="mt-0.5 truncate text-base font-semibold tabular-nums text-rd-heading">
        {value}
      </p>
      {delta !== undefined ? (
        <Delta value={delta} suffix={deltaSuffix} />
      ) : (
        sub && <p className="text-[11px] text-rd-muted">{sub}</p>
      )}
    </div>
  );
}

/** Colored conic performance ring with the exact %. */
function PerfRing({ pct, color }: { pct: number; color: string }) {
  return (
    <div
      className="relative flex h-[92px] w-[92px] items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${color} ${pct}%, hsl(var(--rd-panel)) 0)` }}
    >
      <div className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-rd-card">
        <span className="text-xl font-semibold tabular-nums text-rd-heading">{pct}%</span>
      </div>
    </div>
  );
}
