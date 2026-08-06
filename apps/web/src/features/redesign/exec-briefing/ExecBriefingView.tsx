"use client";

import { CalendarDays, Download, Sparkles } from "lucide-react";
import type { NodeStatus } from "@neo/shared-types";
import { useDashboardData } from "@/features/redesign/dashboard/data";
import { KpiRow } from "./KpiRow";
import { BriefingList } from "./BriefingList";
import { EnterpriseOverview } from "./EnterpriseOverview";
import { EfficiencyPanel } from "./EfficiencyPanel";
import { KeyPerformanceSnapshot } from "./KeyPerformanceSnapshot";
import { ExecRightRail } from "./ExecRightRail";

const COUNT_KEY: Record<NodeStatus, "onTrack" | "atRisk" | "delayed"> = {
  on_track: "onTrack",
  needs_attention: "atRisk",
  not_connected: "delayed",
};

/** todayLabel is computed on the server (in page.tsx) and passed in, so the
 *  date renders identically on both sides — no hydration mismatch. */
export function ExecBriefingView({ todayLabel }: { todayLabel: string }) {
  const d = useDashboardData();

  const pcts = d.projects.map((p) => p.progress_pct).filter((v): v is number => v != null);
  const projectsHealth = pcts.length > 0 ? pcts.reduce((a, b) => a + b, 0) / pcts.length : null;

  const counts = d.projects.reduce(
    (acc, p) => {
      acc[COUNT_KEY[p.status]] += 1;
      return acc;
    },
    { onTrack: 0, atRisk: 0, delayed: 0 },
  );

  return (
    <div className="mx-auto max-w-[1600px] space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
            Executive Briefing
            <Sparkles className="h-5 w-5 text-rd-violet" aria-hidden />
          </h1>
          <p className="mt-1 text-sm text-rd-body">
            Your daily intelligence summary across all companies, projects and functions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-card px-3 py-2 text-sm text-rd-body">
            <CalendarDays className="h-4 w-4 text-rd-cyan" aria-hidden />
            {todayLabel}
          </span>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-4 py-2 text-sm font-semibold text-white transition-[filter] hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
          >
            <Download className="h-4 w-4" aria-hidden />
            Download Briefing
          </button>
        </div>
      </div>

      <KpiRow projectsHealth={projectsHealth} overviewsReady={d.overviewsReady} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <BriefingList
              projectsHealth={projectsHealth}
              counts={counts}
              overviewsReady={d.overviewsReady}
            />
            <div className="space-y-6">
              <EnterpriseOverview />
              <EfficiencyPanel />
            </div>
          </div>
          <KeyPerformanceSnapshot />
        </div>

        <aside className="min-w-0">
          <ExecRightRail />
        </aside>
      </div>
    </div>
  );
}
