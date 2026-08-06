"use client";

import * as React from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

export type SparkColor = "cyan" | "violet" | "green" | "amber" | "rose";

const STROKE: Record<SparkColor, string> = {
  cyan: "hsl(var(--rd-cyan))",
  violet: "hsl(var(--rd-violet))",
  green: "hsl(var(--rd-green))",
  amber: "hsl(var(--rd-amber))",
  rose: "hsl(var(--rd-rose))",
};

export interface SparklineProps {
  /** Series of y-values. */
  data: number[];
  color?: SparkColor;
  height?: number;
  className?: string;
}

/** Tiny filled area chart for trends inside cards. Fills its parent's width. */
export function Sparkline({ data, color = "cyan", height = 44, className }: SparklineProps) {
  const id = React.useId().replace(/:/g, "");
  const stroke = STROKE[color];
  const series = data.map((y, x) => ({ x, y }));

  return (
    <div className={className} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="y"
            stroke={stroke}
            strokeWidth={2}
            fill={`url(#spark-${id})`}
            isAnimationActive={false}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
