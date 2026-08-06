import { MetricCard, MiniBars, SampleTag, SectionHeader } from "@/features/redesign/components";
import { SNAPSHOT } from "./data";

/** 8-card KPI strip. All sample (no live endpoint) — one tag on the header. */
export function KeyPerformanceSnapshot() {
  return (
    <section>
      <SectionHeader title="Key Performance Snapshot" action={<SampleTag />} />
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
