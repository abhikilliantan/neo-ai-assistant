"use client";

import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/cn";
import { Delta, RingGauge, SampleTag, Sparkline } from "@/features/redesign/components";
import { formatCurrency } from "@/features/redesign/components/format";
import { STATUS_PILL, type MergedCompany } from "./data";

export function CompanyCard({ company, index }: { company: MergedCompany; index: number }) {
  return (
    <div className="glow-card p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-rd-grad text-sm font-bold text-white">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-rd-heading">{company.name}</p>
            <p className="truncate text-xs text-rd-muted">{company.descriptor}</p>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
            STATUS_PILL[company.status],
          )}
        >
          {company.status}
        </span>
      </div>

      {/* Body: ring + metrics + sparkline */}
      <div className="mt-4 flex gap-5">
        <div className="flex shrink-0 flex-col items-center gap-1">
          {company.variant === "trading" ? (
            <TradingRing delta={company.portfolioDelta ?? 0} color={company.color === "green"} />
          ) : (
            <RingGauge value={company.ring} size={104} />
          )}
          <span className="text-xs text-rd-muted">
            {company.variant === "trading" ? "Today" : "Health Score"}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          {company.variant === "trading" ? (
            <div className="grid grid-cols-3 gap-3">
              <Metric
                label="Portfolio Value"
                value={company.portfolioValue ?? "—"}
                delta={company.portfolioDelta}
                sample
              />
              <Metric
                label="Daily P&L"
                value={company.dailyPnl ?? "—"}
                delta={company.portfolioDelta}
                sample
              />
              <Metric
                label="Open Positions"
                value={`${company.openPositions ?? 0}`}
                pill="Active"
                pillTone="green"
                sample
              />
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              <Metric
                label="Revenue (MTD)"
                value={formatCurrency(company.revenue ?? 0)}
                delta={company.revenueDelta}
                sample
              />
              <Metric
                label="Employees"
                value={`${company.employees ?? 0}`}
                delta={company.employeesDelta}
                deltaSuffix=""
                sample
              />
              <Metric
                label="Active Projects"
                value={`${company.liveActiveProjects ?? company.activeProjects ?? 0}`}
                pill={company.projectStatus}
                pillTone={company.projectStatus === "At Risk" ? "amber" : "green"}
                sample={company.liveActiveProjects == null}
              />
            </div>
          )}
          <Sparkline data={company.spark} color={company.color} height={44} className="mt-3" />
        </div>
      </div>

      {/* AI insight */}
      <div className="mt-4 border-t border-rd-border pt-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-rd-muted">AI Insight</p>
        <p className="mt-0.5 text-sm text-rd-body">{company.aiInsight}</p>
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="grid flex-1 grid-cols-3 gap-3">
          {company.variant === "trading" ? (
            <>
              <Foot label="Manager" value={company.manager ?? "—"} />
              <Foot label="Strategy" value={company.strategy ?? "—"} />
              <Foot label="Risk Level" value={company.riskLevel ?? "—"} />
            </>
          ) : (
            <>
              <Foot label="CEO" value={company.ceo ?? "—"} />
              <Foot label="Established" value={company.established ?? "—"} />
              <Foot label="Location" value={company.location ?? "—"} />
            </>
          )}
        </div>
        <button
          type="button"
          aria-label="Company actions"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-rd-border text-rd-muted transition-colors hover:border-rd-border-hover hover:text-rd-heading"
        >
          <MoreHorizontal className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  delta,
  deltaSuffix = "%",
  pill,
  pillTone,
  sample,
}: {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  pill?: string;
  pillTone?: "green" | "amber";
  sample?: boolean;
}) {
  return (
    <div className="min-w-0">
      <p className="flex items-center gap-1 truncate text-[11px] text-rd-muted">
        {label}
        {sample && <SampleTag />}
      </p>
      <p className="mt-0.5 truncate text-lg font-semibold tabular-nums text-rd-heading">{value}</p>
      {delta !== undefined && <Delta value={delta} suffix={deltaSuffix} />}
      {pill && (
        <span
          className={cn(
            "mt-0.5 inline-block rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
            pillTone === "amber"
              ? "border-rd-amber/40 bg-rd-amber/10 text-rd-amber"
              : "border-rd-green/40 bg-rd-green/10 text-rd-green",
          )}
        >
          {pill}
        </span>
      )}
    </div>
  );
}

function Foot({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] text-rd-muted">{label}</p>
      <p className="mt-0.5 truncate text-xs font-medium text-rd-heading">{value}</p>
    </div>
  );
}

/** Conic-gradient ring for the trading card — center shows the signed daily %. */
function TradingRing({ delta, color }: { delta: number; color: boolean }) {
  const ring = color ? "hsl(var(--rd-green))" : "hsl(var(--rd-cyan))";
  const pct = Math.min(100, Math.max(6, Math.abs(delta) * 12 + 60)); // visual fill only
  return (
    <div
      className="relative flex items-center justify-center rounded-full"
      style={{
        width: 104,
        height: 104,
        background: `conic-gradient(${ring} ${pct}%, hsl(var(--rd-panel)) 0)`,
      }}
    >
      <div className="flex h-[84px] w-[84px] flex-col items-center justify-center rounded-full bg-rd-card">
        <span className="text-lg font-semibold tabular-nums text-rd-green">
          {delta > 0 ? "+" : ""}
          {delta}%
        </span>
      </div>
    </div>
  );
}
