import type { NodeStatus, ProjectOverview } from "@neo/shared-types";
import { ProjectCard, SampleTag, SectionHeader } from "@/features/redesign/components";
import type { ProjectStatus } from "@/features/redesign/components";
import { SAMPLE_PROJECTS } from "./data";

const STATUS_MAP: Record<NodeStatus, ProjectStatus> = {
  on_track: "on-track",
  needs_attention: "at-risk",
  not_connected: "delayed",
};

interface Props {
  projects: ProjectOverview[];
  overviewsReady: boolean;
}

export function ProjectCommandCenter({ projects, overviewsReady }: Props) {
  const real = overviewsReady && projects.length > 0;
  const realTop = projects.slice(0, 3);

  return (
    <section>
      <SectionHeader
        title="Project Command Center"
        subtitle={real ? "Name, progress & status are live" : undefined}
        action={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rd-green/40 bg-rd-green/10 px-2.5 py-0.5 text-xs font-medium text-rd-green">
              <span className="h-1.5 w-1.5 rounded-full bg-rd-green" aria-hidden />
              12 Online
            </span>
            {!real && <SampleTag />}
          </div>
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {real
          ? realTop.map((p) => (
              <ProjectCard
                key={p.id}
                name={p.name}
                status={STATUS_MAP[p.status]}
                progress={p.progress_pct ?? 0}
                owner="—"
                risk="medium"
                prediction="Owner, risk and AI forecast are not wired to live data yet."
                sample // owner / risk / prediction have no endpoint
              />
            ))
          : SAMPLE_PROJECTS.map((p) => (
              <ProjectCard
                key={p.name}
                name={p.name}
                status={p.status}
                progress={p.progress}
                owner={p.owner}
                risk={p.risk}
                prediction={p.prediction}
                sample
              />
            ))}
      </div>
    </section>
  );
}
