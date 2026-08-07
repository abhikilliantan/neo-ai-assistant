// All sample — Neo has no sales/pipeline backend yet. Every section carries a
// SampleTag (hidden under global Demo mode). Values mirror the Sales Command
// Center mockup.

import type { FunnelRow } from "@/features/redesign/components";

export const CHIPS = [
  "How is sales performing?",
  "Show me my pipeline",
  "Which deals are at risk?",
  "Revenue forecast this quarter",
  "Top performing sales reps",
];

const SP_REV = [62, 70, 66, 78, 74, 86, 90, 88, 100, 96, 112, 124];
const SP_PIPE = [70, 72, 74, 78, 80, 82, 84, 82, 86, 84, 86, 87];
const SP_WON = [40, 44, 42, 48, 52, 50, 60, 64, 70, 74, 88, 92];
const SP_WIN = [24, 25, 24, 26, 27, 26, 28, 27, 29, 28, 29, 29];
const SP_DEAL = [36, 38, 37, 40, 39, 41, 40, 42, 41, 43, 42, 43];

export interface SalesKpi {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  sub: string;
  icon: "revenue" | "pipeline" | "won" | "win" | "deal" | "target";
  color: "cyan" | "violet" | "green" | "amber" | "rose";
  spark?: number[];
  /** target tile renders a ring gauge instead of a sparkline */
  gauge?: number;
}

export const KPIS: SalesKpi[] = [
  {
    label: "Total Revenue (MTD)",
    value: "$1.24M",
    delta: 18.6,
    sub: "vs last month",
    icon: "revenue",
    color: "cyan",
    spark: SP_REV,
  },
  {
    label: "Pipeline Value",
    value: "$8.74M",
    delta: 22.4,
    sub: "vs last month",
    icon: "pipeline",
    color: "violet",
    spark: SP_PIPE,
  },
  {
    label: "Closed Won (MTD)",
    value: "$920K",
    delta: 16.2,
    sub: "vs last month",
    icon: "won",
    color: "green",
    spark: SP_WON,
  },
  {
    label: "Win Rate",
    value: "28.6%",
    delta: 3.7,
    sub: "vs last month",
    icon: "win",
    color: "cyan",
    spark: SP_WIN,
  },
  {
    label: "Avg Deal Size",
    value: "$42.6K",
    delta: 12.8,
    sub: "vs last month",
    icon: "deal",
    color: "amber",
    spark: SP_DEAL,
  },
  {
    label: "Sales Target",
    value: "72%",
    sub: "$8.7M / $12M",
    icon: "target",
    color: "cyan",
    gauge: 72,
  },
];

// Stepped cyan→violet brand ramp (interpolated --rd-cyan 198 93% 60% →
// --rd-violet 258 90% 66%). Shared by the pipeline funnel and the stage donut so
// the two read as one on-brand gradient — no off-brand orange/green/teal.
// Interpolate the brand ramp between --rd-cyan (198 93% 60%) and --rd-violet
// (258 90% 66%) into `n` stepped, on-brand colors — no off-brand orange/green/
// teal. Used by the pipeline funnel, the stage donut, and Deal Health.
function brandRamp(n: number): string[] {
  const from = [198, 93, 60];
  const to = [258, 90, 66];
  return Array.from({ length: n }, (_, i) => {
    const t = n > 1 ? i / (n - 1) : 0;
    const [h, s, l] = from.map((c, k) => Math.round(c + (to[k] - c) * t));
    return `hsl(${h} ${s}% ${l}%)`;
  });
}

export const PIPE_RAMP = brandRamp(5);

// Sales Pipeline funnel
export const PIPELINE: FunnelRow[] = [
  { label: "Prospecting", value: "$2.31M", sub: "265", pct: "68%", color: PIPE_RAMP[0] },
  {
    label: "Qualification",
    value: "$1.89M",
    sub: "158",
    pct: "51%",
    color: PIPE_RAMP[1],
  },
  { label: "Proposal", value: "$2.47M", pct: "38%", color: PIPE_RAMP[2] },
  { label: "Negotiation", value: "$1.45M", sub: "48", pct: "33%", color: PIPE_RAMP[3] },
  { label: "Closed Won", value: "$920K", sub: "32", pct: "67%", color: PIPE_RAMP[4] },
];
export const PIPELINE_TOTAL = "$8.74M";

// Revenue Trend — dual line (revenue vs closed won), values in $K
export const REVENUE_TREND: { label: string; revenue: number; won: number }[] = [
  { label: "Jan", revenue: 640, won: 300 },
  { label: "Feb", revenue: 820, won: 360 },
  { label: "Mar", revenue: 1010, won: 520 },
  { label: "Apr", revenue: 1120, won: 700 },
  { label: "May", revenue: 1240, won: 920 },
];

// Pipeline by Stage donut
export const STAGES: {
  label: string;
  value: number;
  amount: string;
  pct: string;
  color: string;
}[] = [
  {
    label: "Prospecting",
    value: 26.4,
    amount: "$2.31M",
    pct: "26.4%",
    color: PIPE_RAMP[0],
  },
  {
    label: "Qualification",
    value: 21.6,
    amount: "$1.89M",
    pct: "21.6%",
    color: PIPE_RAMP[1],
  },
  { label: "Proposal", value: 28.3, amount: "$2.47M", pct: "28.3%", color: PIPE_RAMP[2] },
  {
    label: "Negotiation",
    value: 16.6,
    amount: "$1.45M",
    pct: "16.6%",
    color: PIPE_RAMP[3],
  },
  {
    label: "Closed Won",
    value: 10.5,
    amount: "$920K",
    pct: "10.5%",
    color: PIPE_RAMP[4],
  },
];

// Forecast vs Target — dual line, values in $M
export const FORECAST: { label: string; target: number; forecast: number }[] = [
  { label: "Jan", target: 2, forecast: 1.8 },
  { label: "Feb", target: 4, forecast: 3.6 },
  { label: "Mar", target: 6, forecast: 5.8 },
  { label: "Apr", target: 9, forecast: 8.4 },
  { label: "May", target: 12, forecast: 11.4 },
];

export interface RepRow {
  name: string;
  role: string;
  deals: number;
  pipeline: string;
  won: string;
  winRate: string;
  score: number;
}

export const REPS: RepRow[] = [
  {
    name: "David Mwangi",
    role: "Sales Director",
    deals: 31,
    pipeline: "$2.14M",
    won: "$340K",
    winRate: "32%",
    score: 92,
  },
  {
    name: "Meera Shah",
    role: "Account Executive",
    deals: 28,
    pipeline: "$1.87M",
    won: "$265K",
    winRate: "29%",
    score: 88,
  },
  {
    name: "Alex Kane",
    role: "Enterprise Sales",
    deals: 24,
    pipeline: "$1.45M",
    won: "$210K",
    winRate: "31%",
    score: 85,
  },
  {
    name: "Priya Nair",
    role: "Account Executive",
    deals: 19,
    pipeline: "$1.12M",
    won: "$135K",
    winRate: "27%",
    score: 78,
  },
  {
    name: "Rakesh Patel",
    role: "Business Dev.",
    deals: 14,
    pipeline: "$870K",
    won: "$90K",
    winRate: "23%",
    score: 72,
  },
];

export const REGIONS: { label: string; value: string; delta: number }[] = [
  { label: "Kenya", value: "$540K", delta: 22 },
  { label: "East Africa", value: "$380K", delta: 18 },
  { label: "EMEA", value: "$210K", delta: 11 },
  { label: "Asia", value: "$90K", delta: -4 },
  { label: "Others", value: "$24K", delta: 7 },
];

// Deal Health is a distribution, not a red/amber alert — recolor to the same
// cyan→violet brand ramp so the whole page reads on-brand. (Semantic red/amber
// stays only on the AI-recommendation alert icons.)
const DEAL_RAMP = brandRamp(4);

export const DEAL_HEALTH: {
  total: number;
  slices: { label: string; count: number; pct: string; color: string }[];
  insight: string;
} = {
  total: 96,
  slices: [
    { label: "Healthy", count: 42, pct: "43.8%", color: DEAL_RAMP[0] },
    { label: "At Risk", count: 32, pct: "33.3%", color: DEAL_RAMP[1] },
    { label: "Critical", count: 12, pct: "12.5%", color: DEAL_RAMP[2] },
    { label: "On Hold", count: 10, pct: "10.4%", color: DEAL_RAMP[3] },
  ],
  insight: "12 deals are at risk of slipping this month. Focus on 3 critical deals worth $1.2M.",
};

export const ACTIVITIES: {
  title: string;
  when: string;
  icon: "demo" | "proposal" | "contract" | "discovery";
  people: string[];
  extra: number;
}[] = [
  {
    title: "Demo with ABC Corp",
    when: "Today, 10:00 AM",
    icon: "demo",
    people: ["Ada N.", "Ben O.", "Cara P."],
    extra: 3,
  },
  {
    title: "Proposal Follow-up",
    when: "Today, 1:30 PM",
    icon: "proposal",
    people: ["Dan Q.", "Eve R."],
    extra: 2,
  },
  {
    title: "Contract Negotiation",
    when: "Tomorrow, 11:00 AM",
    icon: "contract",
    people: ["Fay S.", "Gus T.", "Hana U."],
    extra: 4,
  },
  {
    title: "Discovery Call — Zenith Ltd",
    when: "May 10, 9:00 AM",
    icon: "discovery",
    people: ["Ivy V.", "Jack W."],
    extra: 2,
  },
];

export const OPPORTUNITIES: {
  name: string;
  value: string;
  stage: string;
  priority: "High" | "Medium" | "Low";
}[] = [
  {
    name: "Bidco HR Genie Implementation",
    value: "$1.25M",
    stage: "Negotiation",
    priority: "High",
  },
  { name: "NCBA Bank HR Transformation", value: "$950K", stage: "Proposal", priority: "High" },
  { name: "Unga Group Payroll System", value: "$780K", stage: "Proposal", priority: "Medium" },
  { name: "KPLC Workforce Solution", value: "$620K", stage: "Qualification", priority: "Medium" },
  { name: "Toyota Kenya HR System", value: "$540K", stage: "Qualification", priority: "Low" },
];

export const AI_RECS: { tone: "rose" | "amber" | "green" | "cyan"; text: string }[] = [
  { tone: "rose", text: "Focus on 12 at-risk deals worth $1.2M." },
  { tone: "amber", text: "Engage with inactive leads in the last 14 days." },
  { tone: "green", text: "Upsell opportunity identified in 5 accounts." },
  { tone: "cyan", text: "Increase proposal follow-ups by 20%." },
];

export const QUICK_ACTIONS: {
  label: string;
  icon: "add" | "log" | "report" | "forecast";
}[] = [
  { label: "Add Opportunity", icon: "add" },
  { label: "Log Activity", icon: "log" },
  { label: "Generate Report", icon: "report" },
  { label: "Sales Forecast", icon: "forecast" },
];
