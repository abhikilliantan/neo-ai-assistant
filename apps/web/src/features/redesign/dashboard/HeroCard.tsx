import { Bot, Building2, FolderKanban, Users } from "lucide-react";
import { GlowCard, RingGauge, SampleTag, StatTile } from "@/features/redesign/components";
import { NeoBrain } from "./NeoBrain";

interface HeroCardProps {
  totalCompanies: number;
  companiesReady: boolean;
  activeProjects: number;
  overviewsReady: boolean;
}

export function HeroCard({
  totalCompanies,
  companiesReady,
  activeProjects,
  overviewsReady,
}: HeroCardProps) {
  return (
    <GlowCard className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-rd-heading">
          Good Morning, Abhishek.
        </h1>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-rd-body">
          Your Enterprise is Operating at{" "}
          <span className="font-semibold text-rd-heading">94% Efficiency</span>
          <SampleTag />
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,1.1fr)] lg:items-center">
        {/* AI Intelligence Score */}
        <div className="flex flex-col items-center gap-2">
          <RingGauge value={94} size={150} label="AI Score" />
          <div className="flex items-center gap-1.5">
            <p className="text-xs text-rd-body">AI Intelligence Score</p>
            <SampleTag />
          </div>
        </div>

        {/* Real-where-possible stat tiles */}
        <div className="grid grid-cols-2 gap-3">
          <StatTile
            icon={Building2}
            label="Total Companies"
            value={companiesReady ? totalCompanies : 4}
            sample={!companiesReady}
          />
          <StatTile
            icon={FolderKanban}
            label="Active Projects"
            value={overviewsReady ? activeProjects : 23}
            sample={!overviewsReady}
          />
          <StatTile icon={Bot} label="AI Agents Online" value={12} sample />
          <StatTile icon={Users} label="Employees" value={156} sample />
        </div>

        {/* NEO brain */}
        <NeoBrain />
      </div>
    </GlowCard>
  );
}
