"use client";

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  Building2,
  Gauge,
  LayoutGrid,
  List,
  Plus,
  Search,
  SlidersHorizontal,
  TrendingUp,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Delta, SampleTag } from "@/features/redesign/components";
import { DepartmentCard } from "./DepartmentCard";
import { DepartmentsRightRail } from "./DepartmentsRightRail";
import { KPIS, useDepartmentsData, type MergedDept } from "./data";

const TABS = ["All Departments", "By Performance", "By Headcount", "By Budget", "At Risk"] as const;
type Tab = (typeof TABS)[number];

export function DepartmentsView() {
  const { departments, totalReal } = useDepartmentsData();
  const [view, setView] = useState<"grid" | "list">("grid");
  const [tab, setTab] = useState<Tab>("All Departments");
  const [query, setQuery] = useState("");

  const shown = useMemo(() => arrange(departments, tab, query), [departments, tab, query]);

  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              Departments
              <Building2 className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Monitor performance, resources and KPIs across all departments.
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
          <button
            type="button"
            className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            <SlidersHorizontal className="h-4 w-4" aria-hidden />
            Filter
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-3.5 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add Department
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Kpi
          icon={Building2}
          label="Total Departments"
          value={totalReal != null ? `${totalReal}` : KPIS.total.value}
          delta={KPIS.total.delta}
          deltaSub={KPIS.total.sub}
          sample={totalReal == null}
        />
        <Kpi
          icon={Users}
          label="Total Employees"
          value={KPIS.employees.value}
          delta={KPIS.employees.delta}
          deltaSub="this month"
          sample
        />
        <Kpi
          icon={TrendingUp}
          label="Avg. Performance"
          value={KPIS.avgPerformance.value}
          delta={KPIS.avgPerformance.delta}
          deltaSub="vs last month"
          sample
        />
        <KpiRing
          icon={Gauge}
          label="Budget Utilization"
          value={KPIS.budgetUtil.value}
          pct={KPIS.budgetUtil.pct}
          sub={KPIS.budgetUtil.sub}
          color="hsl(var(--rd-violet))"
        />
        <KpiRing
          icon={Activity}
          label="Overall Efficiency"
          value={KPIS.efficiency.value}
          pct={KPIS.efficiency.pct}
          sub={KPIS.efficiency.sub}
          color="hsl(var(--rd-green))"
        />
        <Kpi
          icon={AlertTriangle}
          label="Departments At Risk"
          value={KPIS.atRisk.value}
          sub={KPIS.atRisk.sub}
          tone="rose"
          sample
        />
      </div>

      {/* Tabs + search */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1 rounded-control border border-rd-border bg-rd-panel/50 p-1">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                tab === t ? "bg-rd-grad text-white" : "text-rd-muted hover:text-rd-heading",
              )}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-rd-muted"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search departments…"
            aria-label="Search departments"
            className="h-10 w-full rounded-control border border-rd-border bg-rd-panel/50 pl-9 pr-3 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30"
          />
        </div>
      </div>

      {/* Cards + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <div
            className={cn(
              "grid gap-4",
              view === "grid" ? "grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3" : "grid-cols-1",
            )}
          >
            {shown.map((d, i) => (
              <DepartmentCard key={d.name} dept={d} index={i} />
            ))}
          </div>
          {shown.length === 0 && (
            <p className="rounded-card border border-rd-border bg-rd-panel/40 py-10 text-center text-sm text-rd-muted">
              No departments match “{query}”.
            </p>
          )}
          <button
            type="button"
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-card border border-rd-border bg-rd-panel/40 py-3 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            Load More Departments
          </button>
        </div>
        <aside className="min-w-0">
          <DepartmentsRightRail />
        </aside>
      </div>
    </div>
  );
}

function arrange(list: MergedDept[], tab: Tab, query: string): MergedDept[] {
  const budgetNum = (d: MergedDept) =>
    Number(d.budget.replace(/[$,KM]/g, "")) * (d.budget.includes("M") ? 1000 : 1);
  let out = [...list];
  if (tab === "By Performance") out.sort((a, b) => b.performance - a.performance);
  else if (tab === "By Headcount") out.sort((a, b) => b.headcount - a.headcount);
  else if (tab === "By Budget") out.sort((a, b) => budgetNum(b) - budgetNum(a));
  else if (tab === "At Risk")
    out = out.filter((d) => d.status === "At Risk" || d.status === "Needs Attention");
  const q = query.trim().toLowerCase();
  if (q)
    out = out.filter(
      (d) => d.name.toLowerCase().includes(q) || d.descriptor.toLowerCase().includes(q),
    );
  return out;
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

function Kpi({
  icon: Icon,
  label,
  value,
  delta,
  deltaSub,
  sub,
  tone,
  sample,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  delta?: number;
  deltaSub?: string;
  sub?: string;
  tone?: "rose";
  sample?: boolean;
}) {
  return (
    <div className="glow-card p-4">
      <div className="flex items-start justify-between gap-2">
        <span
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg border border-rd-border bg-rd-panel",
            tone === "rose" ? "text-rd-rose" : "text-rd-cyan",
          )}
        >
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        {sample && <SampleTag />}
      </div>
      <p className="mt-3 text-xs text-rd-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
      {delta !== undefined ? (
        <div className="mt-0.5 flex items-center gap-1.5">
          <Delta value={delta} suffix={label === "Avg. Performance" ? "%" : ""} />
          {deltaSub && <span className="text-xs text-rd-muted">{deltaSub}</span>}
        </div>
      ) : (
        sub && (
          <p className={cn("mt-0.5 text-xs", tone === "rose" ? "text-rd-rose" : "text-rd-muted")}>
            {sub}
          </p>
        )
      )}
    </div>
  );
}

function KpiRing({
  icon: Icon,
  label,
  value,
  pct,
  sub,
  color,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  pct: number;
  sub: string;
  color: string;
}) {
  return (
    <div className="glow-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs text-rd-muted">
            <Icon className="h-3.5 w-3.5 text-rd-cyan" aria-hidden />
            {label}
            <SampleTag />
          </p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
          <p className="mt-0.5 text-xs text-rd-muted">{sub}</p>
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
    </div>
  );
}
