"use client";

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Building2,
  DollarSign,
  FolderKanban,
  LayoutGrid,
  List,
  Plus,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Delta, RingGauge, SampleTag, Sparkline } from "@/features/redesign/components";
import { CompanyCard } from "./CompanyCard";
import { CompaniesRightRail } from "./CompaniesRightRail";
import { BottomCharts } from "./BottomCharts";
import { SAMPLE_KPIS, useCompaniesData } from "./data";

export function CompaniesView() {
  const data = useCompaniesData();
  const [view, setView] = useState<"grid" | "list">("grid");

  const avgHealth = data.avgHealth != null ? Math.round(data.avgHealth) : SAMPLE_KPIS.avgHealth;
  const projects = data.totalActiveProjects;

  return (
    <div className="mx-auto max-w-[1600px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              Companies
              <Building2 className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Monitor and manage all companies in your enterprise portfolio.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-control border border-rd-border bg-rd-panel/50 p-0.5">
            <ViewToggle
              active={view === "grid"}
              onClick={() => setView("grid")}
              icon={LayoutGrid}
              label="Grid view"
            />
            <ViewToggle
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
            Add Company
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KpiTile
          icon={Building2}
          label="Total Companies"
          value={`${data.totalCompanies}`}
          sub="Active"
          subTone="green"
        />
        <KpiTile
          icon={DollarSign}
          label="Total Revenue (MTD)"
          value={SAMPLE_KPIS.revenue.value}
          delta={SAMPLE_KPIS.revenue.delta}
          deltaSub="vs last month"
          spark
          sample
        />
        <KpiTile
          icon={Users}
          label="Total Employees"
          value={SAMPLE_KPIS.employees.value}
          sub={SAMPLE_KPIS.employees.sub}
          subTone="green"
          sample
        />
        <KpiTile
          icon={FolderKanban}
          label="Total Projects"
          value={projects != null ? `${projects}` : "23"}
          sub="On Track"
          subTone="green"
          sample={projects == null}
        />
        <KpiTile
          icon={Activity}
          label="Avg. Health Score"
          value={`${avgHealth}%`}
          delta={7}
          deltaSub="vs last month"
          ring={avgHealth}
          sample={data.avgHealth == null}
        />
      </div>

      {/* Main: cards + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <div
            className={cn(
              "grid gap-4",
              view === "grid" ? "grid-cols-1 2xl:grid-cols-2" : "grid-cols-1",
            )}
          >
            {data.companies.map((c, i) => (
              <CompanyCard key={c.id} company={c} index={i} />
            ))}
          </div>
          <BottomCharts />
        </div>
        <aside className="min-w-0">
          <CompaniesRightRail data={data} />
        </aside>
      </div>
    </div>
  );
}

function ViewToggle({
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

function KpiTile({
  icon: Icon,
  label,
  value,
  sub,
  subTone,
  delta,
  deltaSub,
  spark,
  ring,
  sample,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  subTone?: "green" | "muted";
  delta?: number;
  deltaSub?: string;
  spark?: boolean;
  ring?: number;
  sample?: boolean;
}) {
  return (
    <div className="glow-card p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        {ring != null ? <RingGauge value={ring} size={40} /> : null}
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-rd-muted">
        {label}
        {sample && <SampleTag />}
      </p>
      <p className="mt-0.5 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
      {delta !== undefined ? (
        <div className="mt-0.5 flex items-center gap-1.5">
          <Delta value={delta} />
          {deltaSub && <span className="text-xs text-rd-muted">{deltaSub}</span>}
        </div>
      ) : (
        sub && (
          <p
            className={cn(
              "mt-0.5 text-xs",
              subTone === "green" ? "text-rd-green" : "text-rd-muted",
            )}
          >
            {sub}
          </p>
        )
      )}
      {spark && (
        <Sparkline
          data={[8, 10, 9, 12, 11, 14, 13, 16, 18, 17, 20, 22]}
          color="cyan"
          height={22}
          className="mt-2"
        />
      )}
    </div>
  );
}
