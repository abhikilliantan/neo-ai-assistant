"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Delta, Donut, RingGauge, SampleTag } from "@/features/redesign/components";
import { EXPENSES, EXPENSES_TOTAL, PL_TREND, PROFIT_TREND } from "./data";

function fmtK(v: number) {
  if (v === 0) return "$0";
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}M` : `$${v}K`;
}

export function FinanceBand() {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <PlTrendCard />
      <ExpenseCard />
      <div className="flex flex-col gap-5">
        <BudgetCard />
        <ProfitCard />
      </div>
    </div>
  );
}

function CardHead({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      {right}
    </div>
  );
}

function PlTrendCard() {
  const [period, setPeriod] = useState("Monthly");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Revenue vs Expenses"
        right={
          <MiniSelect
            value={period}
            onChange={setPeriod}
            options={["Monthly", "Quarterly", "Yearly"]}
          />
        }
      />
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <Legend color="hsl(var(--rd-cyan))" label="Revenue" />
        <Legend color="hsl(var(--rd-violet))" label="Expenses" />
      </div>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={PL_TREND} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="var(--rd-border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={fmtK}
              domain={[0, 1600]}
              ticks={[0, 400, 800, 1200, 1600]}
              width={48}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="hsl(var(--rd-cyan))"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, fill: "hsl(var(--rd-cyan))", strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="expenses"
              stroke="hsl(var(--rd-violet))"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, fill: "hsl(var(--rd-violet))", strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-rd-border pt-4">
        <div>
          <p className="text-[11px] text-rd-muted">Net Margin</p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums text-rd-heading">37.8%</p>
        </div>
        <div>
          <p className="text-[11px] text-rd-muted">MoM Growth</p>
          <Delta value={17.7} className="mt-0.5 text-sm" />
        </div>
        <Stat label="Monthly Burn" value="$820K" tone="text-rd-heading" />
      </div>
    </div>
  );
}

function ExpenseCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Expense Breakdown" />
      <div className="flex items-center gap-4">
        <Donut
          data={EXPENSES.map((s) => ({ label: s.label, value: s.value, color: s.color }))}
          centerValue={EXPENSES_TOTAL}
          centerLabel="Total"
          size={150}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-2">
          {EXPENSES.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="shrink-0 tabular-nums text-rd-muted">{s.pct}</span>
              <span className="w-16 shrink-0 text-right tabular-nums text-rd-heading">
                {s.amount}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BudgetCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Budget Utilization" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col items-center">
          <RingGauge value={74} size={104} />
          <span className="mt-1 text-xs text-rd-muted">$9.2M / $12.4M</span>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <Stat label="Remaining Budget" value="$3.2M" tone="text-rd-heading" />
          <Stat label="Forecast Spend (EOY)" value="$12.1M" tone="text-rd-heading" />
          <Stat label="Projected Variance" value="+$0.3M" tone="text-rd-green" />
        </div>
      </div>
    </div>
  );
}

function ProfitCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Net Profit Trend" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col">
          <span className="text-2xl font-semibold tabular-nums text-rd-heading">$5.6M</span>
          <Delta value={26.4} className="text-sm" />
          <span className="mt-0.5 text-xs text-rd-muted">YTD</span>
        </div>
        <div className="h-[96px] min-w-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={PROFIT_TREND} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <CartesianGrid stroke="var(--rd-border)" vertical={false} />
              <XAxis dataKey="label" hide />
              <YAxis hide domain={[0, 700]} />
              <Line
                type="monotone"
                dataKey="profit"
                stroke="hsl(var(--rd-cyan))"
                strokeWidth={2}
                isAnimationActive={false}
                dot={{ r: 2.5, fill: "hsl(var(--rd-cyan))", strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
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

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-rd-body">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
      {label}
    </span>
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
      aria-label="Period"
      className="h-8 rounded-control border border-rd-border bg-rd-panel/50 px-2 text-xs text-rd-body focus:border-rd-border-hover focus:outline-none"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
