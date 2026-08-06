import { GlowCard } from "./GlowCard";
import { RingGauge } from "./RingGauge";
import { Sparkline, type SparkColor } from "./Sparkline";
import { Delta } from "./Delta";
import { SampleTag } from "./SampleTag";
import { formatCurrency } from "./format";

export interface CompanyStatusCardProps {
  name: string;
  /** Health / status percentage shown in the ring, 0–100. */
  percent: number;
  revenue: number;
  /** Signed revenue change; omit to hide. */
  delta?: number;
  trend: number[];
  color?: SparkColor;
  sample?: boolean;
}

/** Company row: status ring + name + revenue + trend sparkline. */
export function CompanyStatusCard({
  name,
  percent,
  revenue,
  delta,
  trend,
  color = "cyan",
  sample,
}: CompanyStatusCardProps) {
  return (
    <GlowCard>
      <div className="flex items-center gap-4">
        <RingGauge value={percent} size={92} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-sm font-semibold text-rd-heading">{name}</p>
            {sample && <SampleTag className="shrink-0" />}
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-semibold tabular-nums text-rd-heading">
              {formatCurrency(revenue)}
            </span>
            {delta !== undefined && <Delta value={delta} />}
          </div>
          <Sparkline data={trend} color={color} height={36} className="mt-2" />
        </div>
      </div>
    </GlowCard>
  );
}
