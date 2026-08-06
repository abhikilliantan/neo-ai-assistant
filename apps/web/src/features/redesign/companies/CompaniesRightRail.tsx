"use client";

import Image from "next/image";
import {
  ArrowRight,
  Building2,
  ChevronRight,
  FileText,
  GitCompare,
  Plus,
  Sparkles,
  Star,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { SampleTag } from "@/features/redesign/components";
import { formatRelative } from "@/lib/relative-time";
import { SAMPLE_AI_INSIGHTS, SAMPLE_OVERVIEW, SAMPLE_RECENT, type CompaniesData } from "./data";

const INSIGHT_TONE: Record<string, string> = {
  cyan: "text-rd-cyan",
  amber: "text-rd-amber",
  green: "text-rd-green",
  violet: "text-rd-violet",
};

export function CompaniesRightRail({ data }: { data: CompaniesData }) {
  const totalCompanies = data.totalCompanies;
  const projects = data.totalActiveProjects;

  return (
    <div className="space-y-4">
      {/* Company Overview + world map */}
      <div className="glow-card overflow-hidden p-0">
        <div className="flex items-center justify-between px-4 pt-4">
          <h3 className="text-sm font-semibold text-rd-heading">Company Overview</h3>
        </div>
        <div className="relative mt-2 h-32 w-full">
          <Image
            src="/enterprise-globe.png"
            alt=""
            fill
            sizes="360px"
            className="object-cover opacity-80 [mix-blend-mode:screen]"
            aria-hidden
          />
        </div>
        <div className="divide-y divide-rd-border px-4 pb-2">
          <OverviewRow label="Companies" value={`${totalCompanies}`} />
          <OverviewRow label="Employees" value={SAMPLE_OVERVIEW.employees} sample />
          <OverviewRow
            label="Projects"
            value={projects != null ? `${projects}` : `${SAMPLE_OVERVIEW.projects}`}
            sample={projects == null}
            chevron
          />
          <OverviewRow label="Revenue (MTD)" value={SAMPLE_OVERVIEW.revenue} sample chevron />
        </div>
      </div>

      {/* AI Insights */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">AI Insights</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <ul className="space-y-3">
          {SAMPLE_AI_INSIGHTS.map((ins) => (
            <li key={ins.text} className="flex items-start gap-2.5">
              <Sparkles
                className={cn("mt-0.5 h-4 w-4 shrink-0", INSIGHT_TONE[ins.tone])}
                aria-hidden
              />
              <p className="text-sm text-rd-body">{ins.text}</p>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 py-2 text-sm font-medium text-rd-heading transition-colors hover:border-rd-border-hover"
        >
          <Sparkles className="h-4 w-4 text-rd-violet" aria-hidden />
          Generate Company Report
        </button>
      </div>

      {/* Quick Actions */}
      <div className="glow-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-rd-heading">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {[
            { icon: Plus, label: "Add Company" },
            { icon: GitCompare, label: "Compare Companies" },
            { icon: FileText, label: "Company Report" },
            { icon: Star, label: "Performance Review" },
          ].map((a) => (
            <button
              key={a.label}
              type="button"
              className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
            >
              <a.icon className="h-4 w-4 shrink-0 text-rd-cyan" aria-hidden />
              <span className="truncate">{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Recently Updated */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Recently Updated</h3>
            {!data.recentlyUpdated && <SampleTag />}
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <ul className="space-y-1">
          {(data.recentlyUpdated
            ? data.recentlyUpdated.map((r) => ({
                name: r.name,
                ago: `Updated ${formatRelative(r.updatedAt)}`,
              }))
            : SAMPLE_RECENT
          ).map((r) => (
            <li key={r.name}>
              <div className="flex items-center justify-between gap-2 rounded-control px-2 py-2 transition-colors hover:bg-rd-panel/50">
                <span className="flex min-w-0 items-center gap-2.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel">
                    <Building2 className="h-4 w-4 text-rd-cyan" aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-rd-heading">
                      {r.name}
                    </span>
                    <span className="block truncate text-xs text-rd-muted">{r.ago}</span>
                  </span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-rd-muted" aria-hidden />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function OverviewRow({
  label,
  value,
  sample,
  chevron,
}: {
  label: string;
  value: string;
  sample?: boolean;
  chevron?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="flex items-baseline gap-2">
        <span className="text-lg font-semibold tabular-nums text-rd-heading">{value}</span>
        <span className="text-xs text-rd-muted">{label}</span>
        {sample && <SampleTag />}
      </span>
      {chevron ? (
        <ArrowRight className="h-4 w-4 text-rd-muted" aria-hidden />
      ) : (
        <span className="h-4 w-4" />
      )}
    </div>
  );
}
