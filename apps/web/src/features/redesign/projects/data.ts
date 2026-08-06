"use client";

import type { GanttStatus } from "@/features/redesign/components";
import { useDashboardData } from "@/features/redesign/dashboard/data";

export type CardStatus = "On Track" | "At Risk" | "Review" | "Testing" | "Completed";

export interface KanbanCard {
  name: string;
  company: string;
  progress: number;
  status?: CardStatus;
  due?: string;
  owner?: string;
  plannedStart?: string;
  completedOn?: string;
  real?: boolean; // ring/status/progress are live for this card
}

export interface KanbanColumn {
  key: string;
  title: string;
  count: number;
  accent: string; // header text tint
  cards: KanbanCard[];
}

export const STATUS_PILL: Record<CardStatus, string> = {
  "On Track": "border-rd-green/40 bg-rd-green/10 text-rd-green",
  "At Risk": "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  Review: "border-rd-violet/40 bg-rd-violet/10 text-rd-violet",
  Testing: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  Completed: "border-rd-green/40 bg-rd-green/10 text-rd-green",
};

const COLUMNS: KanbanColumn[] = [
  {
    key: "planning",
    title: "Planning",
    count: 3,
    accent: "text-rd-body",
    cards: [
      {
        name: "Mobile App v2.0",
        company: "Skillmind Software",
        progress: 15,
        plannedStart: "20 May 2025",
      },
      { name: "NEO Mobile App", company: "Platform", progress: 10, plannedStart: "01 Jun 2025" },
      {
        name: "AI Recruitment Module",
        company: "HR Genie",
        progress: 5,
        plannedStart: "18 Jun 2025",
      },
    ],
  },
  {
    key: "in-progress",
    title: "In Progress",
    count: 9,
    accent: "text-rd-cyan",
    cards: [
      {
        name: "Bidco HR Genie Implementation",
        company: "Implementation",
        progress: 85,
        status: "On Track",
        due: "15 Aug 2025",
        owner: "Al Kane",
      },
      {
        name: "HR Genie Development",
        company: "Development",
        progress: 62,
        status: "At Risk",
        due: "30 Jun 2025",
        owner: "Aarav K.",
      },
      {
        name: "NEO Platform Enhancement",
        company: "Platform",
        progress: 55,
        status: "At Risk",
        due: "20 Jul 2025",
        owner: "System",
      },
    ],
  },
  {
    key: "review",
    title: "Review",
    count: 5,
    accent: "text-rd-violet",
    cards: [
      {
        name: "Payroll Engine Upgrade",
        company: "HR Genie",
        progress: 75,
        status: "Review",
        due: "25 May 2025",
        owner: "Rakesh",
      },
      {
        name: "Analytics Dashboard",
        company: "NEO Platform",
        progress: 90,
        status: "Review",
        due: "28 May 2025",
        owner: "Al Kane",
      },
      {
        name: "Customer Portal",
        company: "Skillmind Software",
        progress: 65,
        status: "Review",
        due: "05 Jun 2025",
        owner: "Meera",
      },
    ],
  },
  {
    key: "testing",
    title: "Testing",
    count: 3,
    accent: "text-rd-amber",
    cards: [
      {
        name: "TimeTrax Mobile App",
        company: "HR Genie",
        progress: 80,
        status: "Testing",
        due: "10 May 2025",
        owner: "Dev Team",
      },
      {
        name: "Integration Hub",
        company: "Platform",
        progress: 70,
        status: "Testing",
        due: "14 May 2025",
        owner: "Tech Team",
      },
      {
        name: "AI Chatbot Assistant",
        company: "NEO Platform",
        progress: 45,
        status: "Testing",
        due: "22 May 2025",
        owner: "Al Teem",
      },
    ],
  },
  {
    key: "completed",
    title: "Completed",
    count: 3,
    accent: "text-rd-green",
    cards: [
      {
        name: "Leave Management Module",
        company: "HR Genie",
        progress: 100,
        status: "Completed",
        completedOn: "28 Apr 2025",
      },
      {
        name: "Sales CRM Module",
        company: "Skillmind Software",
        progress: 100,
        status: "Completed",
        completedOn: "12 Apr 2025",
      },
      {
        name: "Document Management",
        company: "NEO Platform",
        progress: 100,
        status: "Completed",
        completedOn: "05 Apr 2025",
      },
    ],
  },
];

// ── KPI + bottom + rail sample datasets ─────────────────────────────────────

export const KPIS = {
  total: { value: "23", sub: "4 new", subLabel: "this month" },
  onTrack: { value: "14", pct: 60.9, color: "green" as const },
  atRisk: { value: "6", pct: 26.1, color: "amber" as const },
  delayed: { value: "3", pct: 13, color: "rose" as const },
  avgCompletion: { value: "68%", delta: 8 },
  budget: { value: "$4.82M", pct: 72, of: "$6.7M" },
};

export const TIMELINE_MONTHS = ["May 2025", "Jun 2025", "Jul 2025", "Aug 2025", "Sep 2025"];
export const TIMELINE_ROWS: {
  name: string;
  start: number;
  span: number;
  status: GanttStatus;
  endLabel?: string;
}[] = [
  {
    name: "Bidco HR Genie Implementation",
    start: 0.1,
    span: 3.4,
    status: "on-track",
    endLabel: "15 Aug",
  },
  { name: "HR Genie Development", start: 0.3, span: 1.5, status: "at-risk", endLabel: "30 Jun" },
  {
    name: "NEO Platform Enhancement",
    start: 0.8,
    span: 1.6,
    status: "at-risk",
    endLabel: "20 Jul",
  },
  {
    name: "Payroll Engine Upgrade",
    start: 0.1,
    span: 0.7,
    status: "completed",
    endLabel: "26 May",
  },
  { name: "Mobile App v2.0", start: 0.6, span: 1.0, status: "delayed", endLabel: "20 Jun" },
];

export const RESOURCES = {
  total: "256",
  slices: [
    { label: "Development", value: 128, pct: "50%", color: "hsl(var(--rd-cyan))" },
    { label: "Implementation", value: 64, pct: "25%", color: "hsl(var(--rd-violet))" },
    { label: "Design", value: 32, pct: "12.5%", color: "hsl(var(--rd-green))" },
    { label: "QA & Testing", value: 16, pct: "6.3%", color: "hsl(var(--rd-amber))" },
    { label: "Product Management", value: 16, pct: "6.3%", color: "hsl(var(--rd-rose))" },
  ],
};

export const PREDICTIONS = [
  "18 of 23 projects will be completed on time based on current progress.",
  "3 projects require immediate attention to avoid delays.",
  "Overall project success rate predicted at 87%.",
];

export const RADAR = [
  { axis: "Time", you: 87, industry: 70 },
  { axis: "Budget", you: 72, industry: 68 },
  { axis: "Scope", you: 80, industry: 66 },
  { axis: "Resources", you: 76, industry: 64 },
  { axis: "Quality", you: 90, industry: 72 },
  { axis: "Risk", you: 65, industry: 60 },
];

export const ALERTS: { severity: "HIGH" | "MEDIUM"; title: string }[] = [
  { severity: "HIGH", title: "Bidco implementation may miss deadline by 5 days." },
  { severity: "MEDIUM", title: "3 projects are over budget by > 15%." },
  { severity: "MEDIUM", title: "Resource over-allocation detected in Development team." },
];

// ── Real-data merge ─────────────────────────────────────────────────────────

const STATUS_TO_PILL: Record<string, CardStatus> = {
  on_track: "On Track",
  needs_attention: "At Risk",
  not_connected: "At Risk",
};

/** Kanban columns with the Bidco HR Genie card overridden by live progress +
 *  status when a matching real project exists. Every other value is sample. */
export function useProjectsData(): { columns: KanbanColumn[]; bidcoReal: boolean } {
  const { projects, overviewsReady } = useDashboardData();
  const bidco = overviewsReady
    ? projects.find((p) => /bidco/i.test(p.name) || /hr\s*genie/i.test(p.name))
    : undefined;

  if (!bidco) return { columns: COLUMNS, bidcoReal: false };

  const columns = COLUMNS.map((col) =>
    col.key !== "in-progress"
      ? col
      : {
          ...col,
          cards: col.cards.map((c, i) =>
            i === 0
              ? {
                  ...c,
                  name: bidco.name,
                  progress: bidco.progress_pct ?? c.progress,
                  status: STATUS_TO_PILL[bidco.status] ?? c.status,
                  real: true,
                }
              : c,
          ),
        },
  );
  return { columns, bidcoReal: true };
}
