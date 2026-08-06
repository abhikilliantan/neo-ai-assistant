"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import type { CompanyOverview, CompanySummary } from "@neo/shared-types";
import type { SparkColor } from "@/features/redesign/components";
import { getCompanyOverview, listCompanies } from "@/services/overview";

export type DeptStatus = "Excellent" | "Good" | "At Risk" | "Needs Attention";

export interface Middle {
  label: string;
  value: string;
  sub?: string;
  delta?: number;
}

export interface DeptConfig {
  match: string[];
  name: string;
  descriptor: string;
  status: DeptStatus;
  performance: number;
  color: SparkColor;
  spark: number[];
  headcount: number;
  headcountDelta: number;
  middle: Middle;
  budget: string;
  budgetPct: number;
  lead: string;
  updated: string;
}

export const STATUS_PILL: Record<DeptStatus, string> = {
  Excellent: "border-rd-green/40 bg-rd-green/10 text-rd-green",
  Good: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  "At Risk": "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  "Needs Attention": "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
};

export const RING_COLOR: Record<SparkColor, string> = {
  green: "hsl(var(--rd-green))",
  cyan: "hsl(var(--rd-cyan))",
  violet: "hsl(var(--rd-violet))",
  amber: "hsl(var(--rd-amber))",
  rose: "hsl(var(--rd-rose))",
};

const S1 = [30, 34, 32, 38, 36, 42, 40, 46, 44, 50, 48, 54];
const S2 = [24, 28, 26, 31, 34, 32, 38, 41, 39, 44, 47, 50];
const S3 = [40, 44, 42, 48, 52, 50, 56, 54, 60, 58, 63, 66];
const S4 = [20, 24, 22, 27, 25, 30, 28, 33, 31, 36, 34, 39];

export const DEPARTMENTS: DeptConfig[] = [
  {
    match: ["develop", "engineering"],
    name: "Development",
    descriptor: "Engineering & Product Development",
    status: "Excellent",
    performance: 92,
    color: "green",
    spark: S1,
    headcount: 28,
    headcountDelta: 4,
    middle: { label: "Projects", value: "8", sub: "On Track" },
    budget: "$1.24M",
    budgetPct: 78,
    lead: "Aarav K.",
    updated: "2h",
  },
  {
    match: ["marketing"],
    name: "Marketing",
    descriptor: "Brand & Growth Marketing",
    status: "Good",
    performance: 88,
    color: "violet",
    spark: S2,
    headcount: 14,
    headcountDelta: 2,
    middle: { label: "Campaigns", value: "12", sub: "Active" },
    budget: "$620K",
    budgetPct: 68,
    lead: "Meera S.",
    updated: "1h",
  },
  {
    match: ["sales"],
    name: "Sales",
    descriptor: "Sales & Business Development",
    status: "Excellent",
    performance: 94,
    color: "amber",
    spark: S3,
    headcount: 16,
    headcountDelta: 3,
    middle: { label: "Pipeline", value: "$7.82M", delta: 24.7 },
    budget: "$540K",
    budgetPct: 82,
    lead: "David M.",
    updated: "30m",
  },
  {
    match: ["finance", "accounting"],
    name: "Finance",
    descriptor: "Finance & Accounting",
    status: "Excellent",
    performance: 91,
    color: "green",
    spark: S1,
    headcount: 10,
    headcountDelta: 1,
    middle: { label: "Reports", value: "24", sub: "On Track" },
    budget: "$410K",
    budgetPct: 71,
    lead: "Rakesh P.",
    updated: "1h",
  },
  {
    match: ["hr", "human"],
    name: "HR",
    descriptor: "Human Resources",
    status: "Good",
    performance: 85,
    color: "amber",
    spark: S2,
    headcount: 9,
    headcountDelta: 0,
    middle: { label: "Openings", value: "6", sub: "Active" },
    budget: "$210K",
    budgetPct: 65,
    lead: "Priya N.",
    updated: "2h",
  },
  {
    match: ["implementation"],
    name: "Implementation",
    descriptor: "Project Implementation",
    status: "Good",
    performance: 83,
    color: "cyan",
    spark: S4,
    headcount: 18,
    headcountDelta: 3,
    middle: { label: "Projects", value: "11", sub: "On Track" },
    budget: "$780K",
    budgetPct: 74,
    lead: "Al Kane",
    updated: "1h",
  },
  {
    match: ["customer", "success", "support"],
    name: "Customer Success",
    descriptor: "Customer Experience & Support",
    status: "Good",
    performance: 87,
    color: "violet",
    spark: S2,
    headcount: 12,
    headcountDelta: 1,
    middle: { label: "Tickets", value: "320", delta: -12 },
    budget: "$300K",
    budgetPct: 70,
    lead: "Neha T.",
    updated: "2h",
  },
  {
    match: ["product"],
    name: "Product",
    descriptor: "Product Management",
    status: "Excellent",
    performance: 90,
    color: "green",
    spark: S3,
    headcount: 9,
    headcountDelta: 1,
    middle: { label: "Roadmap", value: "18", sub: "On Track" },
    budget: "$520K",
    budgetPct: 76,
    lead: "Suresh B.",
    updated: "45m",
  },
  {
    match: ["it", "operations", "infrastructure"],
    name: "IT Operations",
    descriptor: "IT & Infrastructure",
    status: "Excellent",
    performance: 96,
    color: "rose",
    spark: S4,
    headcount: 8,
    headcountDelta: 0,
    middle: { label: "Systems", value: "24", sub: "Healthy" },
    budget: "$260K",
    budgetPct: 78,
    lead: "Vikram R.",
    updated: "30m",
  },
];

// ── KPI + right rail sample datasets ────────────────────────────────────────

export const KPIS = {
  total: { value: "12", delta: 1, sub: "new" },
  employees: { value: "156", delta: 12 },
  avgPerformance: { value: "87%", delta: 6 },
  budgetUtil: { value: "72%", pct: 72, sub: "$4.82M / $6.7M" },
  efficiency: { value: "94%", pct: 94, sub: "Excellent" },
  atRisk: { value: "2", sub: "Need attention" },
};

export const OVERVIEW = {
  total: "12",
  buckets: [
    { label: "Excellent", count: 5, pct: "41.7%", color: "hsl(var(--rd-green))" },
    { label: "Good", count: 4, pct: "33.3%", color: "hsl(var(--rd-cyan))" },
    { label: "Needs Attention", count: 2, pct: "16.7%", color: "hsl(var(--rd-amber))" },
    { label: "At Risk", count: 1, pct: "8.3%", color: "hsl(var(--rd-rose))" },
  ],
};

export const INSIGHTS = [
  "Development is the top performing department this month.",
  "Sales revenue increased 24.7% compared to last month.",
  "2 departments need immediate attention.",
  "Overall headcount increased by 12 this month.",
];

export const AT_RISK: { name: string; performance: number; note: string; pill: DeptStatus }[] = [
  { name: "Implementation", performance: 72, note: "High project delays", pill: "At Risk" },
  { name: "HR", performance: 68, note: "High employee attrition", pill: "Needs Attention" },
];

// ── Real-data merge ─────────────────────────────────────────────────────────

const STATUS_TO_DEPT: Record<string, DeptStatus> = {
  on_track: "Excellent",
  needs_attention: "Needs Attention",
  not_connected: "Good",
};

export interface MergedDept extends DeptConfig {
  performanceReal: boolean;
  projectsReal: boolean;
}

export interface DepartmentsData {
  departments: MergedDept[];
  totalReal: number | null; // distinct real department count, else null
}

/** Merge real department names + project counts + progress from the Neo
 *  hierarchy over the sample cards. Headcount/budget/lead stay sample. */
export function useDepartmentsData(): DepartmentsData {
  const companiesQ = useQuery({ queryKey: ["companies"], queryFn: listCompanies, retry: false });
  const companies: CompanySummary[] = companiesQ.data ?? [];
  const overviewQs = useQueries({
    queries: companies.map((c) => ({
      queryKey: ["company-overview", c.id],
      queryFn: () => getCompanyOverview(c.id),
      retry: false,
    })),
  });

  const overviews = overviewQs.map((q) => q.data).filter((d): d is CompanyOverview => Boolean(d));

  // Aggregate real departments by normalized name: sum project counts, keep the
  // richest progress signal. (Each company has its own department records.)
  const realByKey = new Map<
    string,
    { name: string; status: string; projects: number; progress: number | null }
  >();
  for (const ov of overviews) {
    for (const d of ov.departments) {
      const key = d.name.toLowerCase();
      const prev = realByKey.get(key);
      realByKey.set(key, {
        name: d.name,
        status: d.status,
        projects: (prev?.projects ?? 0) + d.project_count,
        progress: d.progress_pct ?? prev?.progress ?? null,
      });
    }
  }
  const realList = [...realByKey.values()];

  const matchReal = (cfg: DeptConfig) =>
    realList.find((r) => cfg.match.some((k) => r.name.toLowerCase().includes(k)));

  const departments: MergedDept[] = DEPARTMENTS.map((cfg) => {
    const real = matchReal(cfg);
    if (!real) return { ...cfg, performanceReal: false, projectsReal: false };
    const isProjectsMiddle = cfg.middle.label === "Projects";
    return {
      ...cfg,
      name: real.name || cfg.name,
      performance: real.progress != null ? Math.round(real.progress) : cfg.performance,
      status: real.progress != null ? (STATUS_TO_DEPT[real.status] ?? cfg.status) : cfg.status,
      middle: isProjectsMiddle ? { ...cfg.middle, value: `${real.projects}` } : cfg.middle,
      performanceReal: real.progress != null,
      projectsReal: isProjectsMiddle,
    };
  });

  return { departments, totalReal: realList.length > 0 ? realList.length : null };
}
