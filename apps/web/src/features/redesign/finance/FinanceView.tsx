"use client";

import { useState } from "react";
import {
  Banknote,
  CircleDollarSign,
  Filter,
  Gauge,
  PiggyBank,
  Percent,
  Plus,
  TrendingUp,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Delta, RingGauge, SampleTag, Sparkline } from "@/features/redesign/components";
import type { SparkColor } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { FinanceBand } from "./FinanceBand";
import { FinanceBottom } from "./FinanceBottom";
import { FinanceRightRail } from "./FinanceRightRail";
import { CHIPS, KPIS } from "./data";

const KPI_ICON: Record<string, LucideIcon> = {
  revenue: CircleDollarSign,
  expense: Banknote,
  profit: PiggyBank,
  cash: Wallet,
  margin: Percent,
  budget: Gauge,
};

const RANGES = ["MTD", "QTD", "YTD"] as const;

export function FinanceView() {
  const [range, setRange] = useState<(typeof RANGES)[number]>("YTD");

  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              Finance Command Center
              <TrendingUp className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Real-time revenue, spend, cash, and financial intelligence.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-control border border-rd-border bg-rd-panel/50 p-0.5">
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(r)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  range === r ? "bg-rd-grad text-white" : "text-rd-body hover:text-rd-heading",
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2 text-sm font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
          >
            <Filter className="h-4 w-4" aria-hidden />
            Filters
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-3.5 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" aria-hidden />
            New Invoice
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
              {k.delta !== undefined ? (
                <div className="mt-0.5 flex items-center gap-1.5">
                  <Delta value={k.delta} suffix={k.deltaSuffix ?? "%"} />
                  <span className="text-xs text-rd-muted">{k.sub}</span>
                </div>
              ) : (
                <p className="mt-0.5 text-xs text-rd-muted">{k.sub}</p>
              )}
              {k.gauge !== undefined ? (
                <div className="mt-2 flex justify-center">
                  <RingGauge value={k.gauge} size={58} />
                </div>
              ) : (
                <Sparkline
                  data={k.spark ?? []}
                  color={k.color as SparkColor}
                  height={26}
                  className="mt-2"
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Main grid: content + right rail */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-5">
          <FinanceBand />
          <FinanceBottom />
        </div>
        <aside className="min-w-0">
          <FinanceRightRail />
        </aside>
      </div>
    </div>
  );
}
