import { MetricCard, MiniBars, SectionHeader } from "@/features/redesign/components";
import { SNAPSHOT } from "./data";
import { SectionSampleChip } from "./DemoMode";

/** 8-card KPI strip. All sample (no live endpoint) — one chip on the header. */
export function KeyPerformanceSnapshot() {
  return (
    <section>
      <SectionHeader title="Key Performance Snapshot" action={<SectionSampleChip />} />
      {/* 4-up (2 rows): 8 across starves each card so values like $1.24M clip. */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {SNAPSHOT.map((m) => (
          <MetricCard
            key={m.label}
            label={m.label}
            value={m.value}
            delta={m.delta}
            deltaSuffix={m.deltaSuffix}
            color={m.color}
            trend={m.bars ? undefined : m.trend}
            chart={m.bars ? <MiniBars data={m.trend} color="amber" height={40} /> : undefined}
          />
        ))}
      </div>
    </section>
  );
}
