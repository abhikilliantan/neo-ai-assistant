"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import type { CompanyOverview, CompanySummary, ProjectOverview } from "@neo/shared-types";
import { getCompanyOverview, listCompanies } from "@/services/overview";
import { listAgents } from "@/services/agents";
import type { SparkColor } from "@/features/redesign/components";

/** Average connected-project progress for a company, or null when nothing is
 *  wired to live data (so we never fabricate a health %). */
function avgProgress(o: CompanyOverview): number | null {
  const pcts = o.departments
    .flatMap((d) => d.projects)
    .map((p) => p.progress_pct)
    .filter((v): v is number => v != null);
  if (pcts.length === 0) return null;
  return pcts.reduce((a, b) => a + b, 0) / pcts.length;
}

export interface CompanyStatus {
  company: CompanySummary;
  /** Real avg progress %, or null when not connected. */
  progress: number | null;
}

/** Pulls every real signal the dashboard can show. Anything not returned here
 *  has no endpoint and must be rendered from SAMPLE_* with a SampleTag. */
export function useDashboardData() {
  const companiesQ = useQuery({ queryKey: ["companies"], queryFn: listCompanies, retry: false });
  const companies = companiesQ.data ?? [];

  const overviewQs = useQueries({
    queries: companies.map((c) => ({
      queryKey: ["company-overview", c.id],
      queryFn: () => getCompanyOverview(c.id),
      retry: false,
    })),
  });

  const agentsQ = useQuery({ queryKey: ["agents"], queryFn: listAgents, retry: false });

  const overviews = overviewQs.map((q) => q.data).filter((d): d is CompanyOverview => Boolean(d));

  const projects: ProjectOverview[] = overviews.flatMap((o) =>
    o.departments.flatMap((d) => d.projects),
  );
  const activeProjects = overviews.reduce((n, o) => n + o.kpis.active_projects, 0);

  const companyStatuses: CompanyStatus[] = companies.map((company, i) => ({
    company,
    progress: overviewQs[i]?.data ? avgProgress(overviewQs[i].data as CompanyOverview) : null,
  }));

  const overviewsReady = companies.length > 0 && overviewQs.every((q) => q.isSuccess);

  return {
    companiesReady: companiesQ.isSuccess,
    totalCompanies: companies.length,
    companyStatuses,
    overviewsReady,
    projects,
    activeProjects,
    agents: agentsQ.data ?? [],
    agentsReady: agentsQ.isSuccess && (agentsQ.data?.length ?? 0) > 0,
  };
}

// ── SAMPLE datasets (no live endpoint — every consumer shows a SampleTag) ────

export const SAMPLE_BRIEFING: {
  label: string;
  value: string;
  sub: string;
  delta?: number;
  tone: "up" | "warn" | "neutral";
}[] = [
  { label: "Revenue (MTD)", value: "$1.24M", sub: "vs last month", delta: 18.6, tone: "up" },
  { label: "Active Projects", value: "23", sub: "On Track", tone: "up" },
  { label: "Today's Meetings", value: "4", sub: "Scheduled", tone: "neutral" },
  { label: "Cash Position", value: "$2.54M", sub: "runway healthy", delta: 8.3, tone: "up" },
  { label: "Critical Risks", value: "3", sub: "Attention", tone: "warn" },
  { label: "CEO Priorities", value: "8", sub: "In Progress", tone: "neutral" },
  { label: "Sales Pipeline", value: "$7.82M", sub: "weighted", delta: 24.7, tone: "up" },
  { label: "Pending Decisions", value: "7", sub: "Awaiting", tone: "warn" },
  { label: "AI Recommendations", value: "5", sub: "New Insights", tone: "neutral" },
];

export const SAMPLE_COMPANY_META: Record<string, { revenue: number; health: string }> = {
  skillmind: { revenue: 542_000, health: "Healthy" },
  abd: { revenue: 324_000, health: "Growing" },
  consulting: { revenue: 210_000, health: "Needs Attention" },
  trading: { revenue: 1_280_000, health: "Stable" },
};

export const SAMPLE_COMPANIES: {
  name: string;
  percent: number;
  revenue: number;
  delta: number;
  color: SparkColor;
}[] = [
  { name: "Skillmind", percent: 92, revenue: 542_000, delta: 6.4, color: "green" },
  { name: "ABD", percent: 88, revenue: 324_000, delta: 4.1, color: "cyan" },
  { name: "Consulting", percent: 76, revenue: 210_000, delta: -1.2, color: "amber" },
  { name: "Trading", percent: 81, revenue: 1_280_000, delta: 3.8, color: "violet" },
];

export const SAMPLE_PROJECTS: {
  name: string;
  status: "on-track" | "at-risk" | "delayed";
  progress: number;
  owner: string;
  risk: "low" | "medium" | "high";
  prediction: string;
}[] = [
  {
    name: "Bidco HR Genie Implementation",
    status: "at-risk",
    progress: 85,
    owner: "S. Kumar",
    risk: "high",
    prediction: "May delay ~5 days — integration testing is the critical path.",
  },
  {
    name: "HR Genie Development",
    status: "on-track",
    progress: 62,
    owner: "Dev Pod A",
    risk: "medium",
    prediction: "Sprint 18 on pace; watch the payroll module scope.",
  },
  {
    name: "NEO Platform",
    status: "on-track",
    progress: 100,
    owner: "Platform",
    risk: "low",
    prediction: "Production stable at 99.98% uptime over the last 30 days.",
  },
];

export const SAMPLE_AGENTS: {
  name: string;
  role: string;
  percent: number;
  status: "active" | "idle" | "offline";
}[] = [
  { name: "CEO Agent", role: "Executive Copilot", percent: 88, status: "active" },
  { name: "Sales Agent", role: "Pipeline & CRM", percent: 74, status: "active" },
  { name: "Finance Agent", role: "Cash & Forecast", percent: 63, status: "active" },
  { name: "Marketing Agent", role: "Campaigns", percent: 57, status: "active" },
  { name: "HR Agent", role: "People Ops", percent: 41, status: "idle" },
  { name: "PMO Agent", role: "Delivery", percent: 69, status: "active" },
  { name: "Dev Agent", role: "Engineering", percent: 82, status: "active" },
  { name: "Impl. Agent", role: "Implementation", percent: 48, status: "idle" },
  { name: "Research Agent", role: "Market Intel", percent: 35, status: "idle" },
  { name: "Content Agent", role: "Copy & Assets", percent: 52, status: "active" },
  { name: "Legal Agent", role: "Contracts", percent: 12, status: "offline" },
  { name: "Support Agent", role: "Customer Care", percent: 66, status: "active" },
];

const trendUp = [12, 15, 14, 19, 22, 21, 26, 30, 29, 34, 38, 44];
const trendDown = [44, 41, 42, 38, 36, 33, 34, 30, 28, 27, 24, 22];

export const SAMPLE_ANALYTICS: {
  label: string;
  value: string;
  delta: number;
  trend: number[];
  color: SparkColor;
}[] = [
  { label: "Revenue", value: "$1.24M", delta: 18.6, trend: trendUp, color: "cyan" },
  { label: "Sales", value: "$412K", delta: 12.3, trend: trendUp, color: "green" },
  { label: "Cash", value: "$2.54M", delta: 8.3, trend: trendUp, color: "cyan" },
  { label: "Projects", value: "23", delta: 4.2, trend: trendUp, color: "violet" },
  { label: "Employees", value: "156", delta: 2.1, trend: trendUp, color: "cyan" },
  { label: "Support Tickets", value: "48", delta: -9.4, trend: trendDown, color: "amber" },
  { label: "Customer Sat", value: "94%", delta: 1.6, trend: trendUp, color: "green" },
  { label: "AI Usage", value: "18.2K", delta: 31.5, trend: trendUp, color: "violet" },
  { label: "Forecast (Q3)", value: "$4.1M", delta: 15.0, trend: trendUp, color: "cyan" },
  { label: "Burn Rate", value: "$318K", delta: -4.8, trend: trendDown, color: "rose" },
];

export const SAMPLE_MEETINGS: { time: string; title: string; who: string }[] = [
  { time: "10:00", title: "Bidco steering committee", who: "S. Kumar +4" },
  { time: "12:30", title: "Sales pipeline review", who: "Sales pod" },
  { time: "15:00", title: "Finance — cash forecast", who: "CFO office" },
  { time: "16:30", title: "1:1 — Head of HR", who: "N. Sharma" },
];

export const SAMPLE_ALERTS: { severity: "HIGH" | "MEDIUM" | "LOW"; title: string; meta: string }[] =
  [
    { severity: "HIGH", title: "Bidco implementation — delay risk (~5 days)", meta: "PMO" },
    { severity: "MEDIUM", title: "2 employees need attention (utilisation)", meta: "HR" },
    { severity: "MEDIUM", title: "Server utilisation trending high", meta: "Ops" },
  ];

export const SAMPLE_RECS: string[] = [
  "Rebalance 2 engineers onto Bidco integration to protect the go-live.",
  "Accelerate 3 warm deals in pipeline — forecast upside ~$180K.",
  "Review payroll module scope; likely the next schedule risk.",
];

export const SAMPLE_INSIGHTS: string[] = [
  "Revenue growth is outpacing burn — runway extended to ~14 months.",
  "Customer satisfaction up 1.6pts after the latest release.",
  "AI usage +31% MoM; agents are absorbing more routine ops load.",
];
