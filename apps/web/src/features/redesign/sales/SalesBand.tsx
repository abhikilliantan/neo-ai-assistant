"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Delta, Donut, Funnel, RingGauge, SampleTag } from "@/features/redesign/components";
import { FORECAST, PIPELINE, PIPELINE_TOTAL, REVENUE_TREND, STAGES } from "./data";

function fmtK(v: number) {
  if (v === 0) return "$0";
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}M` : `$${v}K`;
}

export function SalesBand() {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <PipelineCard />
      <RevenueTrendCard />
      <div className="flex flex-col gap-5">
        <StageCard />
        <ForecastCard />
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

function PipelineCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Sales Pipeline" />
      <p className="mb-3 text-center text-xs text-rd-muted">
        Total Pipeline{" "}
        <span className="text-base font-semibold text-rd-heading">{PIPELINE_TOTAL}</span>
      </p>
      <Funnel rows={PIPELINE} pctHeader="Conv." className="flex-1" />
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-rd-border pt-4">
        <Stat label="Overall Conversion Rate" value="28.6%" tone="text-rd-green" />
        <Stat label="Avg. Sales Cycle" value="32 Days" tone="text-rd-heading" />
      </div>
    </div>
  );
}

function RevenueTrendCard() {
  const [period, setPeriod] = useState("Monthly");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Revenue Trend"
        right={
          <MiniSelect
            value={period}
            onChange={setPeriod}
            options={["Monthly", "Weekly", "Daily"]}
          />
        }
      />
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
        <Legend color="hsl(var(--rd-cyan))" label="Revenue" />
        <Legend color="hsl(var(--rd-green))" label="Closed Won" />
      </div>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={REVENUE_TREND} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
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
              domain={[0, 1500]}
              ticks={[0, 300, 600, 900, 1200, 1500]}
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
              dataKey="won"
              stroke="hsl(var(--rd-green))"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, fill: "hsl(var(--rd-green))", strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-rd-border pt-4">
        <div>
          <p className="text-[11px] text-rd-muted">This Month vs Last</p>
          <Delta value={18.6} className="mt-0.5 text-sm" />
        </div>
        <Stat label="Forecast (May)" value="$1.45M" tone="text-rd-heading" />
        <Stat label="Variance to Target" value="-$260K" tone="text-rd-rose" />
      </div>
    </div>
  );
}

function StageCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Pipeline by Stage" />
      <div className="flex items-center gap-4">
        <Donut
          data={STAGES.map((s) => ({ label: s.label, value: s.value, color: s.color }))}
          centerValue={PIPELINE_TOTAL}
          centerLabel="Total"
          size={150}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-2">
          {STAGES.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="shrink-0 tabular-nums text-rd-muted">{s.pct}</span>
              <span className="w-14 shrink-0 text-right tabular-nums text-rd-heading">
                {s.amount}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ForecastCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Forecast vs Target" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col items-center">
          <RingGauge value={72} size={104} />
          <span className="mt-1 text-xs text-rd-muted">$8.7M / $12M</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap justify-end gap-x-4 gap-y-1 text-xs">
            <Legend color="hsl(var(--rd-muted))" label="Target" dashed />
            <Legend color="hsl(var(--rd-green))" label="Forecast" />
          </div>
          <div className="h-[120px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={FORECAST} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
                <CartesianGrid stroke="var(--rd-border)" vertical={false} />
                <XAxis dataKey="label" hide />
                <YAxis hide domain={[0, 12]} />
                <Line
                  type="monotone"
                  dataKey="target"
                  stroke="hsl(var(--rd-muted))"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  isAnimationActive={false}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="forecast"
                  stroke="hsl(var(--rd-green))"
                  strokeWidth={2}
                  isAnimationActive={false}
                  dot={{ r: 2.5, fill: "hsl(var(--rd-green))", strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
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

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-rd-body">
      <span
        className="h-2 w-2 rounded-full"
        style={{
          background: dashed ? "transparent" : color,
          border: dashed ? `1px dashed ${color}` : undefined,
        }}
        aria-hidden
      />
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
