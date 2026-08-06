"use client";

import * as React from "react";
import { Bar, BarChart, Cell, ResponsiveContainer } from "recharts";

export type BarColor = "amber" | "cyan" | "violet" | "green";

const FILL: Record<BarColor, string> = {
  amber: "hsl(var(--rd-amber))",
  cyan: "hsl(var(--rd-cyan))",
  violet: "hsl(var(--rd-violet))",
  green: "hsl(var(--rd-green))",
};

export interface MiniBarsProps {
  data: number[];
  color?: BarColor;
  height?: number;
  className?: string;
}

/** Tiny bar chart for count-style metrics (e.g. headcount). Fills parent width. */
export function MiniBars({ data, color = "amber", height = 44, className }: MiniBarsProps) {
  const fill = FILL[color];
  const max = Math.max(...data, 1);
  const series = data.map((y, x) => ({ x, y }));

  return (
    <div className={className} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={series}
          margin={{ top: 2, right: 0, bottom: 0, left: 0 }}
          barCategoryGap={2}
        >
          <Bar dataKey="y" radius={[2, 2, 0, 0]} isAnimationActive={false}>
            {series.map((d) => (
              // Taller bars brighter, shorter dimmer — reads as a mini histogram.
              <Cell key={d.x} fill={fill} fillOpacity={0.35 + 0.65 * (d.y / max)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
