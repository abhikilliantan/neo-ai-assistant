"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

export interface DonutSlice {
  label: string;
  value: number;
  color: string; // CSS color (e.g. "hsl(var(--rd-cyan))")
}

export interface DonutProps {
  data: DonutSlice[];
  /** Big number in the middle. */
  centerValue: string;
  centerLabel?: string;
  size?: number;
  className?: string;
}

/** Donut ring with a centered total. Legend is rendered by the caller so it can
 *  match each mockup's layout. Built on recharts' PieChart. */
export function Donut({ data, centerValue, centerLabel, size = 170, className }: DonutProps) {
  return (
    <div className={className} style={{ position: "relative", width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={size * 0.62}
            outerRadius={size * 0.9}
            paddingAngle={2}
            stroke="none"
            startAngle={90}
            endAngle={-270}
            isAnimationActive={false}
          >
            {data.map((s) => (
              <Cell key={s.label} fill={s.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tabular-nums text-rd-heading">{centerValue}</span>
        {centerLabel && <span className="text-xs text-rd-muted">{centerLabel}</span>}
      </div>
    </div>
  );
}
