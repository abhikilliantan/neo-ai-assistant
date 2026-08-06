"use client";

import {
  CalendarClock,
  GitFork,
  LogOut,
  Plane,
  Plus,
  Upload,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Delta, SampleTag, Sparkline } from "@/features/redesign/components";
import type { SparkColor } from "@/features/redesign/components";
import { EmployeeDirectory } from "./EmployeeDirectory";
import { MiddleCards } from "./MiddleCards";
import { PeopleRightRail } from "./PeopleRightRail";
import { CHIPS, KPIS } from "./data";

const KPI_ICON: Record<string, LucideIcon> = {
  total: Users,
  active: UserCheck,
  hires: UserPlus,
  leave: Plane,
  attrition: LogOut,
  tenure: CalendarClock,
};

export function PeopleView() {
  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              People
              <Users className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Manage your most valuable asset. Empower your people. Scale your enterprise.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <HeaderBtn icon={GitFork} label="Org Chart" />
          <HeaderBtn icon={Upload} label="Import" />
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-3.5 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add Employee
          </button>
        </div>
      </div>

      {/* Quick-question chips */}
      <div className="flex flex-wrap gap-2">
        {CHIPS.map((c) => (
          <button
            key={c}
            type="button"
            className="rounded-full border border-rd-border bg-rd-panel/60 px-3.5 py-1.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            {c}
          </button>
        ))}
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {KPIS.map((k) => {
          const Icon = KPI_ICON[k.icon];
          return (
            <div key={k.label} className="glow-card p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <SampleTag />
              </div>
              <p className="mt-3 text-xs uppercase tracking-wide text-rd-muted">{k.label}</p>
              <p className="mt-0.5 text-2xl font-semibold tabular-nums text-rd-heading">
                {k.value}
              </p>
              <div className="mt-0.5 flex items-center gap-1.5">
                {k.delta !== undefined ? (
                  <>
                    <Delta value={k.delta} suffix={k.deltaSuffix ?? "%"} />
                    <span className="text-xs text-rd-muted">{k.sub}</span>
                  </>
                ) : (
                  <span className="text-xs text-rd-muted">{k.sub}</span>
                )}
              </div>
              <Sparkline
                data={k.spark}
                color={k.color as SparkColor}
                height={26}
                className="mt-2"
              />
            </div>
          );
        })}
      </div>

      {/* Middle 3 cards */}
      <MiddleCards />

      {/* Directory + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <EmployeeDirectory />
        </div>
        <aside className="min-w-0">
          <PeopleRightRail />
        </aside>
      </div>
    </div>
  );
}

function HeaderBtn({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
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
