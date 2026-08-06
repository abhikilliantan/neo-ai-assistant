"use client";

import * as React from "react";
import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";
import { cn } from "@/lib/cn";
import { round } from "./format";

export interface RingGaugeProps {
  /** 0–100 percentage. */
  value: number;
  /** Diameter in px. */
  size?: number;
  /** Center label under the value (e.g. "healthy"). */
  label?: string;
  className?: string;
}

/** Radial gauge with the signature cyan→violet gradient stroke and a centered
 *  value. Built on recharts' RadialBarChart. */
export function RingGauge({ value, size = 132, label, className }: RingGaugeProps) {
  // Unique gradient id per instance so multiple gauges don't share one def.
  const id = React.useId().replace(/:/g, "");
  const pct = Math.max(0, Math.min(100, value));

  return (
    <div className={cn("relative", className)} style={{ width: size, height: size }}>
      <RadialBarChart
        width={size}
        height={size}
        data={[{ value: pct }]}
        innerRadius="76%"
        outerRadius="100%"
        startAngle={90}
        endAngle={-270}
      >
        <defs>
          <linearGradient id={`ring-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="hsl(var(--rd-cyan))" />
            <stop offset="100%" stopColor="hsl(var(--rd-violet))" />
          </linearGradient>
        </defs>
        <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
        <RadialBar
          dataKey="value"
          cornerRadius={size / 2}
          background={{ fill: "hsl(var(--rd-panel))" }}
          fill={`url(#ring-${id})`}
        />
      </RadialBarChart>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tabular-nums text-rd-heading">{round(pct)}%</span>
        {label && <span className="mt-0.5 text-xs text-rd-body">{label}</span>}
      </div>
    </div>
  );
}
