"use client";

import { useState } from "react";
import {
  BarChart3,
  ChevronDown,
  DollarSign,
  Filter,
  Gauge,
  Megaphone,
  Percent,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Delta, SampleTag, Sparkline } from "@/features/redesign/components";
import type { SparkColor } from "@/features/redesign/components";
import { MarketingMiddle } from "./MarketingMiddle";
import { MarketingBottom } from "./MarketingBottom";
import { MarketingRightRail } from "./MarketingRightRail";
import { CHIPS, KPIS } from "./data";

const KPI_ICON: Record<string, LucideIcon> = {
  spend: DollarSign,
  leads: Users,
  qualified: UserCheck,
  conversion: Percent,
  roi: TrendingUp,
  pipeline: BarChart3,
};

export function MarketingView() {
  const [range, setRange] = useState("Custom");

  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              Marketing Command Center
              <Megaphone className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Real-time marketing performance, campaigns, and growth intelligence.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm text-rd-body">
            May 1 – May 7, 2025
            <ChevronDown className="h-4 w-4 text-rd-muted" aria-hidden />
          </span>
          <MiniSelect
            value={range}
            onChange={setRange}
            options={["Custom", "This Week", "This Month"]}
          />
          <button
            type="button"
            className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            <Filter className="h-4 w-4" aria-hidden />
            Filters
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
          const Icon = KPI_ICON[k.icon] ?? Gauge;
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
                <Delta value={k.delta} suffix={k.deltaSuffix ?? "%"} />
                <span className="text-xs text-rd-muted">{k.sub}</span>
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

      {/* Middle band: channels / funnel / campaigns */}
      <MarketingMiddle />

      {/* Content + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <MarketingBottom />
        </div>
        <aside className="min-w-0">
          <MarketingRightRail />
        </aside>
      </div>
    </div>
  );
}

function MiniSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Date range preset"
      className="h-9 rounded-control border border-rd-border bg-rd-panel/50 px-2.5 text-sm text-rd-body focus:border-rd-border-hover focus:outline-none"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
