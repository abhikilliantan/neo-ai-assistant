"use client";

import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { SampleTag } from "@/features/redesign/components";
import { PERF_LINES, PERF_SERIES, SAMPLE_DISTRIBUTION } from "./data";

export function BottomCharts() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      {/* Performance overview — multi-line */}
      <div className="glow-card p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">Company Performance Overview</h3>
          <SampleTag />
        </div>
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {PERF_LINES.map((l) => (
            <span key={l.key} className="flex items-center gap-1.5 text-xs text-rd-body">
              <span className="h-2 w-2 rounded-full" style={{ background: l.color }} aria-hidden />
              {l.name}
            </span>
          ))}
        </div>
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={PERF_SERIES} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
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
                tickFormatter={(v) => `${v}%`}
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
              />
              {PERF_LINES.map((l) => (
                <Line
                  key={l.key}
                  type="monotone"
                  dataKey={l.key}
                  stroke={l.color}
                  strokeWidth={2}
                  isAnimationActive={false}
                  dot={{ r: 2.5, fill: l.color, strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Performance distribution — donut */}
      <div className="glow-card p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">Performance Distribution</h3>
          <SampleTag />
        </div>
        <div className="flex items-center gap-5">
          <div className="relative h-[150px] w-[150px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={SAMPLE_DISTRIBUTION.buckets}
                  dataKey="count"
                  nameKey="label"
                  innerRadius={48}
                  outerRadius={70}
                  paddingAngle={3}
                  stroke="none"
                  startAngle={90}
                  endAngle={-270}
                  isAnimationActive={false}
                >
                  {SAMPLE_DISTRIBUTION.buckets.map((b) => (
                    <Cell key={b.label} fill={b.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-semibold text-rd-heading">
                {SAMPLE_DISTRIBUTION.total}
              </span>
              <span className="text-xs text-rd-muted">Total</span>
            </div>
          </div>
          <ul className="min-w-0 flex-1 space-y-3">
            {SAMPLE_DISTRIBUTION.buckets.map((b) => (
              <li key={b.label} className="flex items-center gap-2.5">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: b.color }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 text-sm text-rd-body">
                  <span className="font-semibold text-rd-heading">{b.count}</span> {b.label}{" "}
                  <span className="text-rd-muted">({b.range})</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
