import type { Agent } from "@neo/shared-types";
import { AgentCard, SampleTag, SectionHeader } from "@/features/redesign/components";
import { SAMPLE_AGENTS } from "./data";

interface Props {
  agents: Agent[];
  agentsReady: boolean;
}

export function AiAgents({ agents, agentsReady }: Props) {
  // Real agent names/roles when the roster loads; load% + status stay sample.
  const cards =
    agentsReady && agents.length > 0
      ? agents.slice(0, 12).map((a, i) => ({
          name: a.name,
          role: a.description || SAMPLE_AGENTS[i % SAMPLE_AGENTS.length].role,
          percent: SAMPLE_AGENTS[i % SAMPLE_AGENTS.length].percent,
          status: SAMPLE_AGENTS[i % SAMPLE_AGENTS.length].status,
        }))
      : SAMPLE_AGENTS;

  return (
    <section>
      <SectionHeader
        title="AI Agents"
        subtitle={agentsReady ? "Roster is live; load & status are sample" : undefined}
        action={<SampleTag />}
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {cards.map((a) => (
          <AgentCard
            key={a.name}
            name={a.name}
            role={a.role}
            percent={a.percent}
            status={a.status}
          />
        ))}
      </div>
    </section>
  );
}
