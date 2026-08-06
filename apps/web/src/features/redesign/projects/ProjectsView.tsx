"use client";

import type { LucideIcon } from "lucide-react";
import { ChevronDown, LayoutGrid, List, Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Delta, SampleTag, Sparkline } from "@/features/redesign/components";
import { KanbanBoard } from "./KanbanBoard";
import { ProjectsBottomRow } from "./ProjectsBottomRow";
import { ProjectsRightRail } from "./ProjectsRightRail";
import { KPIS, useProjectsData } from "./data";

const SPARK_UP = [8, 10, 9, 12, 11, 14, 13, 16, 15, 18, 20, 22];
const SPARK_COMP = [40, 44, 48, 52, 55, 58, 60, 63, 65, 66, 67, 68];

export function ProjectsView() {
  const { columns } = useProjectsData();
  const [view, setView] = useState<"grid" | "list">("grid");

  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-rd-heading">Projects</h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Monitor, manage and deliver all enterprise projects with AI-powered intelligence.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-control border border-rd-border bg-rd-panel/50 p-0.5">
            <Toggle
              active={view === "grid"}
              onClick={() => setView("grid")}
              icon={LayoutGrid}
              label="Grid view"
            />
            <Toggle
              active={view === "list"}
              onClick={() => setView("list")}
              icon={List}
              label="List view"
            />
          </div>
          <HeaderButton icon={SlidersHorizontal} label="Filter" />
          <button
            type="button"
            className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            All Projects
            <ChevronDown className="h-4 w-4" aria-hidden />
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-3.5 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" aria-hidden />
            New Project
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Kpi
          label="Total Projects"
          value={KPIS.total.value}
          sub={KPIS.total.sub}
          subLabel={KPIS.total.subLabel}
          subTone="green"
          spark={SPARK_UP}
          sample
        />
        <KpiRing
          label="On Track"
          value={KPIS.onTrack.value}
          pct={KPIS.onTrack.pct}
          color="hsl(var(--rd-green))"
        />
        <KpiRing
          label="At Risk"
          value={KPIS.atRisk.value}
          pct={KPIS.atRisk.pct}
          color="hsl(var(--rd-amber))"
        />
        <KpiRing
          label="Delayed"
          value={KPIS.delayed.value}
          pct={KPIS.delayed.pct}
          color="hsl(var(--rd-rose))"
        />
        <Kpi
          label="Avg. Completion"
          value={KPIS.avgCompletion.value}
          delta={KPIS.avgCompletion.delta}
          deltaSub="vs last month"
          spark={SPARK_COMP}
          sample
        />
        <KpiBudget />
      </div>

      {/* Command center kanban */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-rd-muted">
          Project Command Center
        </h2>
        <KanbanBoard columns={columns} />
      </section>

      {/* Bottom + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <ProjectsBottomRow />
        </div>
        <aside className="min-w-0">
          <ProjectsRightRail />
        </aside>
      </div>
    </div>
  );
}

function Toggle({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
        active ? "bg-rd-grad text-white" : "text-rd-muted hover:text-rd-heading",
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
    </button>
  );
}

function HeaderButton({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <button
      type="button"
      className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
    >
      <Icon className="h-4 w-4" aria-hidden />
      {label}
    </button>
  );
}

function Kpi({
  label,
  value,
  sub,
  subLabel,
  subTone,
  delta,
  deltaSub,
  spark,
  sample,
}: {
  label: string;
  value: string;
  sub?: string;
  subLabel?: string;
  subTone?: "green";
  delta?: number;
  deltaSub?: string;
  spark?: number[];
  sample?: boolean;
}) {
  return (
    <div className="glow-card p-4">
      <p className="flex items-center gap-1.5 text-xs text-rd-muted">
        {label}
        {sample && <SampleTag />}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
      {delta !== undefined ? (
        <div className="mt-0.5 flex items-center gap-1.5">
          <Delta value={delta} />
          {deltaSub && <span className="text-xs text-rd-muted">{deltaSub}</span>}
        </div>
      ) : (
        sub && (
          <p className="mt-0.5 text-xs">
            <span className={subTone === "green" ? "text-rd-green" : "text-rd-body"}>↑ {sub}</span>{" "}
            <span className="text-rd-muted">{subLabel}</span>
          </p>
        )
      )}
      {spark && <Sparkline data={spark} color="cyan" height={24} className="mt-2" />}
    </div>
  );
}

function KpiRing({
  label,
  value,
  pct,
  color,
}: {
  label: string;
  value: string;
  pct: number;
  color: string;
}) {
  return (
    <div className="glow-card flex items-center justify-between gap-2 p-4">
      <div>
        <p className="flex items-center gap-1.5 text-xs text-rd-muted">
          {label}
          <SampleTag />
        </p>
        <p className="mt-1 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
      </div>
      <div
        className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full"
        style={{ background: `conic-gradient(${color} ${pct}%, hsl(var(--rd-panel)) 0)` }}
      >
        <span className="flex h-[42px] w-[42px] items-center justify-center rounded-full bg-rd-card text-[11px] font-semibold tabular-nums text-rd-heading">
          {pct}%
        </span>
      </div>
    </div>
  );
}

function KpiBudget() {
  return (
    <div className="glow-card p-4">
      <p className="flex items-center gap-1.5 text-xs text-rd-muted">
        Budget Utilization
        <SampleTag />
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-rd-heading">
        {KPIS.budget.value}
      </p>
      <p className="mt-0.5 text-xs text-rd-muted">
        {KPIS.budget.pct}% of {KPIS.budget.of}
      </p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-rd-panel">
        <div className="h-full rounded-full bg-rd-grad" style={{ width: `${KPIS.budget.pct}%` }} />
      </div>
    </div>
  );
}
