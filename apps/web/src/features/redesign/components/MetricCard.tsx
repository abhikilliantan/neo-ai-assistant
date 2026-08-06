import * as React from "react";
import { GlowCard } from "./GlowCard";
import { Delta } from "./Delta";
import { SampleTag } from "./SampleTag";
import { Sparkline, type SparkColor } from "./Sparkline";
import { round } from "./format";

export interface MetricCardProps {
  label: string;
  value: number | string;
  /** Signed change; omit to hide the delta. */
  delta?: number;
  /** Unit shown after the delta (default "%"). Use "" for raw counts/points. */
  deltaSuffix?: string;
  trend?: number[];
  color?: SparkColor;
  /** Custom chart node; overrides the built-in sparkline (e.g. bars). */
  chart?: React.ReactNode;
  sample?: boolean;
}

/** Label + value + delta over a colored sparkline (or a custom chart). */
export function MetricCard({
  label,
  value,
  delta,
  deltaSuffix,
  trend,
  color = "cyan",
  chart,
  sample,
}: MetricCardProps) {
  return (
    <GlowCard>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <p className="text-sm text-rd-body">{label}</p>
          {sample && <SampleTag />}
        </div>
        {delta !== undefined && <Delta value={delta} suffix={deltaSuffix} />}
      </div>
      <p className="mt-1 text-3xl font-semibold tabular-nums text-rd-heading">
        {typeof value === "number" ? round(value) : value}
      </p>
      {(chart || trend) && (
        <div className="mt-3">{chart ?? <Sparkline data={trend!} color={color} />}</div>
      )}
    </GlowCard>
  );
}
