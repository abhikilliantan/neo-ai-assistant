"use client";

import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from "recharts";

export interface RadarStatPoint {
  axis: string;
  you: number;
  industry: number;
}

export interface RadarStatProps {
  data: RadarStatPoint[];
  height?: number;
  className?: string;
}

/** Two-series radar (your value vs an industry baseline) over labelled axes.
 *  Values are 0–100. Built on recharts' RadarChart. */
export function RadarStat({ data, height = 240, className }: RadarStatProps) {
  return (
    <div className={className} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%" margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <PolarGrid stroke="var(--rd-border)" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "hsl(var(--rd-muted))", fontSize: 10 }} />
          <Radar
            name="Industry Avg."
            dataKey="industry"
            stroke="hsl(var(--rd-muted))"
            strokeDasharray="4 3"
            fill="hsl(var(--rd-muted))"
            fillOpacity={0.06}
            isAnimationActive={false}
          />
          <Radar
            name="Your Projects"
            dataKey="you"
            stroke="hsl(var(--rd-cyan))"
            fill="hsl(var(--rd-cyan))"
            fillOpacity={0.22}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
