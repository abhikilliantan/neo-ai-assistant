import { ArrowUpRight } from "lucide-react";
import { LineTrend, RingGauge } from "@/features/redesign/components";
import { EFFICIENCY_TREND } from "./data";
import { SectionSampleChip } from "./DemoMode";

export function EfficiencyPanel() {
  return (
    <div className="glow-card p-5">
      {/* Efficiency score */}
      <div className="mb-3 flex items-center gap-2">
        <span className="h-5 w-1 rounded-full bg-rd-grad" aria-hidden />
        <h3 className="text-sm font-semibold uppercase tracking-wide text-rd-heading">
          Enterprise Efficiency Score
        </h3>
        <SectionSampleChip />
      </div>
      <div className="flex flex-col items-center">
        <RingGauge value={94} size={150} label="Excellent" />
        <span className="mt-2 flex items-center gap-1 text-xs font-medium text-rd-green">
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          +7% vs yesterday
        </span>
      </div>

      {/* Trend */}
      <div className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-rd-body">Efficiency Trend (7 Days)</h3>
        </div>
        <LineTrend data={EFFICIENCY_TREND} unit="%" height={200} />
      </div>
    </div>
  );
}
