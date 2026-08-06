import { GlowCard, Delta, SampleTag, SectionHeader } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { round } from "@/features/redesign/components/format";
import { SAMPLE_BRIEFING } from "./data";

const TONE: Record<"up" | "warn" | "neutral", string> = {
  up: "text-rd-green",
  warn: "text-rd-amber",
  neutral: "text-rd-muted",
};

interface Props {
  activeProjects: number;
  overviewsReady: boolean;
}

export function ExecutiveBriefing({ activeProjects, overviewsReady }: Props) {
  return (
    <section>
      <SectionHeader
        title="Today's Executive Briefing"
        subtitle="Key numbers across the enterprise"
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {SAMPLE_BRIEFING.map((t) => {
          // "Active Projects" is the one tile with a real backing endpoint.
          const isProjects = t.label === "Active Projects";
          const real = isProjects && overviewsReady;
          const value = real ? round(activeProjects) : t.value;
          return (
            <GlowCard key={t.label} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <p className="text-sm text-rd-body">{t.label}</p>
                  {!real && <SampleTag />}
                </div>
                {t.delta !== undefined && <Delta value={t.delta} />}
              </div>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
              <p className={cn("mt-0.5 text-xs", TONE[t.tone])}>{t.sub}</p>
            </GlowCard>
          );
        })}
      </div>
    </section>
  );
}
