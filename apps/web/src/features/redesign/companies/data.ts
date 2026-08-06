"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import type { CompanyOverview, CompanySummary } from "@neo/shared-types";
import type { SparkColor } from "@/features/redesign/components";
import { getCompanyOverview, listCompanies } from "@/services/overview";

export type StatusLabel = "Healthy" | "Growing" | "Needs Attention" | "Excellent";

// Per-company mockup values. Financials/descriptors/AI-insight are SAMPLE (no
// endpoint); the health ring % and active-project count get overridden with
// live values when a company's overview is connected (see useCompaniesData).
export interface CompanyConfig {
  /** keywords matched (case-insensitive) against the real company name. */
  match: string[];
  variant: "standard" | "trading";
  name: string; // fallback display name when the API returns nothing
  descriptor: string;
  status: StatusLabel;
  percent: number; // sample health ring
  color: SparkColor;
  spark: number[];
  aiInsight: string;
  // standard
  revenue?: number;
  revenueDelta?: number;
  employees?: number;
  employeesDelta?: number;
  activeProjects?: number;
  projectStatus?: "On Track" | "At Risk";
  ceo?: string;
  established?: string;
  location?: string;
  // trading
  portfolioValue?: string;
  portfolioDelta?: number;
  dailyPnl?: string;
  openPositions?: number;
  manager?: string;
  strategy?: string;
  riskLevel?: string;
}

const UP = [30, 33, 31, 36, 34, 40, 39, 44, 47, 45, 51, 55];
const UP2 = [24, 27, 26, 30, 29, 33, 36, 34, 39, 43, 46, 50];
const DOWN = [48, 46, 47, 43, 40, 41, 37, 35, 33, 30, 28, 25];
const STRONG = [20, 24, 28, 27, 33, 38, 42, 46, 52, 58, 63, 70];

export const COMPANY_CONFIGS: CompanyConfig[] = [
  {
    match: ["skillmind"],
    variant: "standard",
    name: "Skillmind Software Ltd",
    descriptor: "Software Products & SaaS",
    status: "Healthy",
    percent: 92,
    color: "cyan",
    spark: UP,
    aiInsight: "Strong revenue growth driven by HR Genie SaaS subscriptions.",
    revenue: 542_000,
    revenueDelta: 16.4,
    employees: 108,
    employeesDelta: 8,
    activeProjects: 8,
    projectStatus: "On Track",
    ceo: "Abhishek Kiliyantan",
    established: "2020",
    location: "Nairobi, Kenya",
  },
  {
    match: ["consulting"],
    variant: "standard",
    name: "ABD Consulting",
    descriptor: "Consulting & Advisory",
    status: "Needs Attention",
    percent: 76,
    color: "amber",
    spark: DOWN,
    aiInsight: "Project delays impacting utilization. Look into resource allocation.",
    revenue: 210_000,
    revenueDelta: -5.2,
    employees: 42,
    employeesDelta: 0,
    activeProjects: 5,
    projectStatus: "At Risk",
    ceo: "Abhishek Kiliyantan",
    established: "2018",
    location: "Nairobi, Kenya",
  },
  {
    match: ["trading", "portfolio"],
    variant: "trading",
    name: "Trading Portfolio",
    descriptor: "Investments & Trading",
    status: "Excellent",
    percent: 96,
    color: "green",
    spark: STRONG,
    aiInsight: "Markets are favorable. Consider increasing position in indices.",
    portfolioValue: "$1.28M",
    portfolioDelta: 3.8,
    dailyPnl: "+$47.3K",
    openPositions: 12,
    manager: "Abhishek Kiliyantan",
    strategy: "Balanced Growth",
    riskLevel: "Moderate",
  },
  {
    // ABD Limited — keep last so "consulting" matches ABD Consulting first.
    match: ["abd", "limited"],
    variant: "standard",
    name: "ABD Limited",
    descriptor: "Technology & AI Solutions",
    status: "Growing",
    percent: 88,
    color: "violet",
    spark: UP2,
    aiInsight: "Strong momentum in enterprise solutions and implementation services.",
    revenue: 324_000,
    revenueDelta: 12.8,
    employees: 76,
    employeesDelta: 5,
    activeProjects: 6,
    projectStatus: "On Track",
    ceo: "Abhishek Kiliyantan",
    established: "2022",
    location: "Nairobi, Kenya",
  },
];

// Display order matches the mockup (Skillmind, ABD Limited, ABD Consulting, Trading).
const DISPLAY_ORDER = ["skillmind", "abd limited", "abd consulting", "trading"];

export function pickConfig(name: string): CompanyConfig {
  const n = name.toLowerCase();
  // "consulting" and "trading" are distinctive; check them before the generic
  // "abd" fallback so ABD Consulting doesn't get mistaken for ABD Limited.
  const order = ["skillmind", "consulting", "trading", "abd"];
  for (const key of order) {
    const cfg = COMPANY_CONFIGS.find((c) => c.match.includes(key));
    if (cfg && n.includes(key)) return cfg;
  }
  return COMPANY_CONFIGS[0];
}

export interface MergedCompany extends CompanyConfig {
  id: string;
  ring: number; // real avg progress when connected, else sample percent
  ringIsReal: boolean;
  liveActiveProjects: number | null; // real active_projects, else null
  updatedAt: string | null;
}

/** Average connected-project progress, or null when nothing is wired live. */
function avgProgress(o: CompanyOverview): number | null {
  const pcts = o.departments
    .flatMap((d) => d.projects)
    .map((p) => p.progress_pct)
    .filter((v): v is number => v != null);
  if (pcts.length === 0) return null;
  return pcts.reduce((a, b) => a + b, 0) / pcts.length;
}

export interface CompaniesData {
  ready: boolean; // real company list loaded
  companies: MergedCompany[];
  totalCompanies: number;
  totalActiveProjects: number | null; // real sum, else null
  avgHealth: number | null; // real avg across connected companies, else null
  recentlyUpdated: { id: string; name: string; updatedAt: string }[] | null;
}

/** Real company names + connected overview metrics, merged over the sample
 *  config. Anything not returned here stays sample (and carries a SampleTag). */
export function useCompaniesData(): CompaniesData {
  const companiesQ = useQuery({ queryKey: ["companies"], queryFn: listCompanies, retry: false });
  const companies: CompanySummary[] = companiesQ.data ?? [];

  const overviewQs = useQueries({
    queries: companies.map((c) => ({
      queryKey: ["company-overview", c.id],
      queryFn: () => getCompanyOverview(c.id),
      retry: false,
    })),
  });

  const ready = companiesQ.isSuccess && companies.length > 0;

  if (!ready) {
    // Fall back to the four sample companies so the page still matches the
    // mockup (every value carries a SampleTag when Demo mode is off).
    return {
      ready: false,
      companies: COMPANY_CONFIGS.map((cfg, i) => ({
        ...cfg,
        id: `sample-${i}`,
        ring: cfg.percent,
        ringIsReal: false,
        liveActiveProjects: null,
        updatedAt: null,
      })),
      totalCompanies: COMPANY_CONFIGS.length,
      totalActiveProjects: null,
      avgHealth: null,
      recentlyUpdated: null,
    };
  }

  const merged: MergedCompany[] = companies.map((c, i) => {
    const cfg = pickConfig(c.name);
    const ov = overviewQs[i]?.data;
    const progress = ov ? avgProgress(ov) : null;
    return {
      ...cfg,
      name: c.name,
      id: c.id,
      ring: progress ?? cfg.percent,
      ringIsReal: progress != null,
      liveActiveProjects: ov ? ov.kpis.active_projects : null,
      updatedAt: ov ? ov.updated_at : null,
    };
  });
  merged.sort(
    (a, b) =>
      DISPLAY_ORDER.indexOf(pickOrderKey(a.name)) - DISPLAY_ORDER.indexOf(pickOrderKey(b.name)),
  );

  const connected = merged.filter((m) => m.ringIsReal).map((m) => m.ring);
  const avgHealth =
    connected.length > 0 ? connected.reduce((a, b) => a + b, 0) / connected.length : null;

  const liveProjects = merged
    .map((m) => m.liveActiveProjects)
    .filter((v): v is number => v != null);
  const totalActiveProjects =
    liveProjects.length > 0 ? liveProjects.reduce((a, b) => a + b, 0) : null;

  const updated = merged
    .filter((m): m is MergedCompany & { updatedAt: string } => m.updatedAt != null)
    .map((m) => ({ id: m.id, name: m.name, updatedAt: m.updatedAt }))
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  return {
    ready: true,
    companies: merged,
    totalCompanies: companies.length,
    totalActiveProjects,
    avgHealth,
    recentlyUpdated: updated.length > 0 ? updated : null,
  };
}

function pickOrderKey(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("skillmind")) return "skillmind";
  if (n.includes("consulting")) return "abd consulting";
  if (n.includes("trading") || n.includes("portfolio")) return "trading";
  if (n.includes("abd")) return "abd limited";
  return "skillmind";
}

// ── Sample-only datasets (no live endpoint) ─────────────────────────────────

export const SAMPLE_KPIS = {
  revenue: { value: "$1.24M", delta: 18.6 },
  employees: { value: "256", sub: "12 new this month" },
  avgHealth: 85,
};

export const SAMPLE_OVERVIEW = {
  companies: 4,
  employees: "256",
  projects: 23,
  revenue: "$1.24M",
};

export const SAMPLE_AI_INSIGHTS: { tone: "cyan" | "amber" | "green" | "violet"; text: string }[] = [
  { tone: "cyan", text: "ABD Limited has 88% health score and high growth potential." },
  { tone: "amber", text: "Consulting company needs attention due to project delays." },
  { tone: "green", text: "Skillmind Software is performing exceptionally well." },
  { tone: "violet", text: "Trading portfolio is up 3.8% today." },
];

export const SAMPLE_RECENT = [
  { name: "ABD Limited", ago: "Updated 5 min ago" },
  { name: "Skillmind Software Ltd", ago: "Updated 15 min ago" },
  { name: "Trading Portfolio", ago: "Updated 30 min ago" },
  { name: "ABD Consulting", ago: "Updated 1 hr ago" },
];

export const SAMPLE_DISTRIBUTION = {
  total: 4,
  buckets: [
    { label: "Excellent", range: "≥90%", count: 2, color: "hsl(var(--rd-green))" },
    { label: "Good", range: "70-89%", count: 1, color: "hsl(var(--rd-cyan))" },
    { label: "Needs Attention", range: "<70%", count: 1, color: "hsl(var(--rd-amber))" },
  ],
};

// Per-company performance series (health % over the last 8 days).
export const PERF_SERIES: {
  label: string;
  skillmind: number;
  abd: number;
  consulting: number;
  trading: number;
}[] = [
  { label: "30 Apr", skillmind: 74, abd: 60, consulting: 55, trading: 30 },
  { label: "1 May", skillmind: 76, abd: 63, consulting: 54, trading: 38 },
  { label: "2 May", skillmind: 79, abd: 66, consulting: 52, trading: 47 },
  { label: "3 May", skillmind: 82, abd: 70, consulting: 50, trading: 55 },
  { label: "4 May", skillmind: 85, abd: 74, consulting: 47, trading: 62 },
  { label: "5 May", skillmind: 88, abd: 78, consulting: 44, trading: 70 },
  { label: "6 May", skillmind: 90, abd: 83, consulting: 42, trading: 78 },
  { label: "7 May", skillmind: 92, abd: 88, consulting: 40, trading: 85 },
];

export const PERF_LINES: {
  key: "skillmind" | "abd" | "consulting" | "trading";
  name: string;
  color: string;
}[] = [
  { key: "skillmind", name: "Skillmind Software", color: "hsl(var(--rd-cyan))" },
  { key: "abd", name: "ABD Limited", color: "hsl(var(--rd-violet))" },
  { key: "consulting", name: "ABD Consulting", color: "hsl(var(--rd-amber))" },
  { key: "trading", name: "Trading Portfolio", color: "hsl(var(--rd-green))" },
];

export const STATUS_PILL: Record<StatusLabel, string> = {
  Healthy: "border-rd-green/40 bg-rd-green/10 text-rd-green",
  Growing: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
  "Needs Attention": "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  Excellent: "border-rd-green/40 bg-rd-green/10 text-rd-green",
};
