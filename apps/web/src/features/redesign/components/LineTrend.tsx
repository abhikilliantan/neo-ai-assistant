"use client";

import * as React from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";

export interface LineTrendPoint {
  label: string;
  value: number;
}

export interface LineTrendProps {
  data: LineTrendPoint[];
  height?: number;
  /** Y axis suffix, e.g. "%". */
  unit?: string;
  className?: string;
}

/** Labelled line chart with dots + grid — the "trend over N days" panel. */
export function LineTrend({ data, height = 200, unit = "", className }: LineTrendProps) {
  return (
    <div className={className} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--rd-border)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            width={46}
            tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}${unit}`}
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="hsl(var(--rd-cyan))"
            strokeWidth={2}
            isAnimationActive={false}
            dot={{ r: 3, fill: "hsl(var(--rd-cyan))", strokeWidth: 0 }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
