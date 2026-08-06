import { GlowCard } from "./GlowCard";
import { Delta } from "./Delta";
import { Sparkline, type SparkColor } from "./Sparkline";
import { round } from "./format";

export interface MetricCardProps {
  label: string;
  value: number | string;
  /** Signed percentage change; omit to hide the delta. */
  delta?: number;
  trend: number[];
  color?: SparkColor;
  sample?: boolean;
}

/** Label + value + delta over a colored sparkline. */
export function MetricCard({
  label,
  value,
  delta,
  trend,
  color = "cyan",
  sample,
}: MetricCardProps) {
  return (
    <GlowCard sample={sample}>
      <div className="flex items-start justify-between">
        <p className="text-sm text-rd-body">{label}</p>
        {delta !== undefined && <Delta value={delta} />}
      </div>
      <p className="mt-1 text-3xl font-semibold tabular-nums text-rd-heading">
        {typeof value === "number" ? round(value) : value}
      </p>
      <Sparkline data={trend} color={color} className="mt-3" />
    </GlowCard>
  );
}
