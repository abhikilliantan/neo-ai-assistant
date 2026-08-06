import { MetricCard, SampleTag, SectionHeader } from "@/features/redesign/components";
import { SAMPLE_ANALYTICS } from "./data";

/** All metrics here (revenue, cash, sales, tickets, forecast, burn…) have no
 *  live endpoint yet, so the whole strip is sample. */
export function RealtimeAnalytics() {
  return (
    <section>
      <SectionHeader
        title="Real-Time Analytics"
        subtitle="Trends across the business"
        action={<SampleTag />}
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {SAMPLE_ANALYTICS.map((m) => (
          <MetricCard
            key={m.label}
            label={m.label}
            value={m.value}
            delta={m.delta}
            trend={m.trend}
            color={m.color}
          />
        ))}
      </div>
    </section>
  );
}
