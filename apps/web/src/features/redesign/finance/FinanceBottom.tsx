"use client";

import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { Delta, Donut, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { DEPT_BUDGETS, FIN_HEALTH, STREAMS } from "./data";

export function FinanceBottom() {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <BudgetTableCard />
      <StreamsCard />
      <HealthCard />
    </div>
  );
}

function CardHead({
  title,
  selects,
}: {
  title: string;
  selects?: { value: string; onChange: (v: string) => void; options: string[] }[];
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      {selects && (
        <div className="flex items-center gap-2">
          {selects.map((s, i) => (
            <MiniSelect key={i} {...s} />
          ))}
        </div>
      )}
    </div>
  );
}

function BudgetTableCard() {
  const [period, setPeriod] = useState("This Year");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Budget by Department"
        selects={[{ value: period, onChange: setPeriod, options: ["This Year", "This Quarter"] }]}
      />
      <div className="-mx-2 flex-1 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-rd-muted">
              <th className="px-2 py-2 font-medium">Department</th>
              <th className="px-2 py-2 text-right font-medium">Budget</th>
              <th className="px-2 py-2 text-right font-medium">Spent</th>
              <th className="px-2 py-2 text-right font-medium">Remaining</th>
              <th className="px-2 py-2 font-medium">Utilization</th>
            </tr>
          </thead>
          <tbody>
            {DEPT_BUDGETS.map((d) => (
              <tr key={d.name} className="border-t border-rd-border/60">
                <td className="px-2 py-2.5 text-sm font-medium text-rd-heading">{d.name}</td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {d.budget}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-heading">
                  {d.spent}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {d.remaining}
                </td>
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 min-w-[54px] flex-1 overflow-hidden rounded-full bg-rd-panel">
                      <div
                        className="h-full rounded-full bg-rd-grad"
                        style={{ width: `${d.util}%` }}
                      />
                    </div>
                    <span className="w-9 shrink-0 text-right text-xs tabular-nums text-rd-body">
                      {d.util}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <FooterLink label="View full budget" />
    </div>
  );
}

function StreamsCard() {
  const [period, setPeriod] = useState("This Year");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Revenue by Stream"
        selects={[{ value: period, onChange: setPeriod, options: ["This Year", "This Quarter"] }]}
      />
      <ul className="flex-1 space-y-3">
        {STREAMS.map((s) => (
          <li key={s.label} className="flex items-center gap-2 text-sm">
            <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
            <span className="shrink-0 tabular-nums text-rd-heading">{s.value}</span>
            <Delta value={s.delta} className="w-14 justify-end" />
          </li>
        ))}
      </ul>
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-rd-border pt-4">
        <Stat label="Recurring Revenue" value="62%" tone="text-rd-heading" />
        <Stat label="Net Revenue Retention" value="118%" tone="text-rd-green" />
      </div>
    </div>
  );
}

function HealthCard() {
  const [scope, setScope] = useState("All Budgets");
  const { total, slices, insight } = FIN_HEALTH;
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Financial Health"
        selects={[{ value: scope, onChange: setScope, options: ["All Budgets", "Over Budget"] }]}
      />
      <div className="flex items-center gap-4">
        <Donut
          data={slices.map((s) => ({ label: s.label, value: s.count, color: s.color }))}
          centerValue={total}
          centerLabel="Spend"
          size={128}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-2">
          {slices.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-sm">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="w-12 shrink-0 text-right tabular-nums text-rd-muted">({s.pct})</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-4 rounded-card border border-rd-border bg-rd-panel/40 p-3">
        <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-rd-cyan">
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          AI Insight
        </div>
        <p className="text-xs text-rd-body">{insight}</p>
      </div>
      <FooterLink label="View over-budget items" />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div>
      <p className="text-[11px] text-rd-muted">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function FooterLink({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-control border border-rd-border py-2.5 text-sm font-medium text-rd-cyan transition-colors hover:border-rd-border-hover"
    >
      {label}
      <ArrowRight className="h-4 w-4" aria-hidden />
    </button>
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
      aria-label="Filter"
      className={cn(
        "h-8 rounded-control border border-rd-border bg-rd-panel/50 px-2 text-xs text-rd-body",
        "focus:border-rd-border-hover focus:outline-none",
      )}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
