"use client";

import { useDashboardData } from "./data";
import { HeroCard } from "./HeroCard";
import { ExecutiveBriefing } from "./ExecutiveBriefing";
import { LiveCompanyStatus } from "./LiveCompanyStatus";
import { ProjectCommandCenter } from "./ProjectCommandCenter";
import { AiAgents } from "./AiAgents";
import { RealtimeAnalytics } from "./RealtimeAnalytics";
import { RightRail } from "./RightRail";

export function DashboardView() {
  const d = useDashboardData();

  return (
    <div className="mx-auto max-w-[1600px] space-y-6">
      <HeroCard
        totalCompanies={d.totalCompanies}
        companiesReady={d.companiesReady}
        activeProjects={d.activeProjects}
        overviewsReady={d.overviewsReady}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-8">
          <ExecutiveBriefing activeProjects={d.activeProjects} overviewsReady={d.overviewsReady} />
          <LiveCompanyStatus
            companyStatuses={d.companyStatuses}
            companiesReady={d.companiesReady}
          />
          <ProjectCommandCenter projects={d.projects} overviewsReady={d.overviewsReady} />
          <AiAgents agents={d.agents} agentsReady={d.agentsReady} />
          <RealtimeAnalytics />
        </div>

        <aside className="min-w-0">
          <RightRail />
        </aside>
      </div>
    </div>
  );
}
