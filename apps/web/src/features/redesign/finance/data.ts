// All sample — Neo has no finance/accounting backend yet. Every section carries
// a SampleTag (hidden under global Demo mode). Values mirror the Finance
// Command Center mockup. Charts use the cyan→violet brand ramp ONLY.

import type { FunnelRow } from "@/features/redesign/components";

export const CHIPS = [
  "How is our cash flow?",
  "Show me the P&L",
  "Which departments are over budget?",
  "Revenue forecast this quarter",
  "Largest expenses this month",
];

const SP_REV = [820, 900, 880, 1010, 1080, 1120, 1180, 1240, 1210, 1320, 1380, 1460];
const SP_EXP = [560, 590, 610, 640, 660, 690, 700, 720, 740, 760, 790, 820];
const SP_PROFIT = [260, 310, 270, 370, 420, 430, 480, 520, 470, 560, 590, 640];
const SP_CASH = [300, 320, 310, 340, 360, 350, 370, 380, 375, 390, 388, 392];
const SP_MARGIN = [56, 57, 56, 58, 59, 60, 60, 61, 61, 62, 62, 62];

export interface FinanceKpi {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  sub: string;
  icon: "revenue" | "expense" | "profit" | "cash" | "margin" | "budget";
  color: "cyan" | "violet";
  spark?: number[];
  /** budget tile renders a ring gauge instead of a sparkline */
  gauge?: number;
}

export const KPIS: FinanceKpi[] = [
  {
    label: "Total Revenue (YTD)",
    value: "$14.8M",
    delta: 18.6,
    sub: "vs last year",
    icon: "revenue",
    color: "cyan",
    spark: SP_REV,
  },
  {
    label: "Total Expenses (YTD)",
    value: "$9.2M",
    delta: 11.2,
    sub: "vs last year",
    icon: "expense",
    color: "violet",
    spark: SP_EXP,
  },
  {
    label: "Net Profit (YTD)",
    value: "$5.6M",
    delta: 26.4,
    sub: "vs last year",
    icon: "profit",
    color: "cyan",
    spark: SP_PROFIT,
  },
  {
    label: "Cash Balance",
    value: "$3.9M",
    delta: 8.1,
    sub: "vs last month",
    icon: "cash",
    color: "violet",
    spark: SP_CASH,
  },
  {
    label: "Gross Margin",
    value: "62.4%",
    delta: 3.2,
    sub: "vs last year",
    icon: "margin",
    color: "cyan",
    spark: SP_MARGIN,
  },
  {
    label: "Budget Utilization",
    value: "74%",
    sub: "$9.2M / $12.4M",
    icon: "budget",
    color: "cyan",
    gauge: 74,
  },
];

// Interpolate the brand ramp between --rd-cyan (198 93% 60%) and --rd-violet
// (258 90% 66%) into `n` stepped, on-brand colors — no off-brand orange/green.
function brandRamp(n: number): string[] {
  const from = [198, 93, 60];
  const to = [258, 90, 66];
  return Array.from({ length: n }, (_, i) => {
    const t = n > 1 ? i / (n - 1) : 0;
    const [h, s, l] = from.map((c, k) => Math.round(c + (to[k] - c) * t));
    return `hsl(${h} ${s}% ${l}%)`;
  });
}

const EXP_RAMP = brandRamp(5);

// Revenue vs Expenses — dual line (values in $K)
export const PL_TREND: { label: string; revenue: number; expenses: number }[] = [
  { label: "Jan", revenue: 980, expenses: 620 },
  { label: "Feb", revenue: 1080, expenses: 660 },
  { label: "Mar", revenue: 1180, expenses: 700 },
  { label: "Apr", revenue: 1240, expenses: 740 },
  { label: "May", revenue: 1460, expenses: 820 },
];

// Expense Breakdown donut
export const EXPENSES: {
  label: string;
  value: number;
  amount: string;
  pct: string;
  color: string;
}[] = [
  { label: "Payroll", value: 46, amount: "$4.23M", pct: "46%", color: EXP_RAMP[0] },
  { label: "Operations", value: 22, amount: "$2.02M", pct: "22%", color: EXP_RAMP[1] },
  { label: "Marketing", value: 15, amount: "$1.38M", pct: "15%", color: EXP_RAMP[2] },
  { label: "R&D", value: 11, amount: "$1.01M", pct: "11%", color: EXP_RAMP[3] },
  { label: "Other", value: 6, amount: "$0.55M", pct: "6%", color: EXP_RAMP[4] },
];
export const EXPENSES_TOTAL = "$9.2M";

// Net Profit Trend — single line (values in $K)
export const PROFIT_TREND: { label: string; profit: number }[] = [
  { label: "Jan", profit: 360 },
  { label: "Feb", profit: 420 },
  { label: "Mar", profit: 480 },
  { label: "Apr", profit: 500 },
  { label: "May", profit: 640 },
];

export interface DeptBudget {
  name: string;
  budget: string;
  spent: string;
  remaining: string;
  util: number;
}

export const DEPT_BUDGETS: DeptBudget[] = [
  { name: "Engineering", budget: "$4.20M", spent: "$3.35M", remaining: "$0.85M", util: 80 },
  { name: "Sales", budget: "$2.60M", spent: "$1.95M", remaining: "$0.65M", util: 75 },
  { name: "Marketing", budget: "$1.80M", spent: "$1.53M", remaining: "$0.27M", util: 85 },
  { name: "Operations", budget: "$2.10M", spent: "$1.36M", remaining: "$0.74M", util: 65 },
  { name: "G&A", budget: "$1.70M", spent: "$1.02M", remaining: "$0.68M", util: 60 },
];

export const STREAMS: { label: string; value: string; delta: number }[] = [
  { label: "Subscriptions", value: "$7.4M", delta: 24 },
  { label: "Professional Services", value: "$3.9M", delta: 15 },
  { label: "Licenses", value: "$2.1M", delta: 9 },
  { label: "Support", value: "$1.1M", delta: 6 },
  { label: "Other", value: "$0.3M", delta: -3 },
];

// Financial Health — distribution recolored to the cyan→violet ramp (semantic
// red/amber stays only on AI-recommendation alert icons).
const HEALTH_RAMP = brandRamp(4);

export const FIN_HEALTH: {
  total: string;
  slices: { label: string; count: number; pct: string; color: string }[];
  insight: string;
} = {
  total: "$9.2M",
  slices: [
    { label: "On Budget", count: 58, pct: "58%", color: HEALTH_RAMP[0] },
    { label: "Watch", count: 24, pct: "24%", color: HEALTH_RAMP[1] },
    { label: "Over Budget", count: 12, pct: "12%", color: HEALTH_RAMP[2] },
    { label: "Frozen", count: 6, pct: "6%", color: HEALTH_RAMP[3] },
  ],
  insight:
    "Marketing is trending 85% utilized with 6 weeks left — reallocate $0.2M or freeze non-essential spend.",
};

export const PAYMENTS: {
  title: string;
  when: string;
  amount: string;
  icon: "invoice" | "payroll" | "tax" | "vendor";
}[] = [
  { title: "Payroll Run — May", when: "Today", amount: "$1.84M", icon: "payroll" },
  { title: "VAT Remittance", when: "May 12", amount: "$420K", icon: "tax" },
  { title: "AWS + SaaS Renewals", when: "May 15", amount: "$96K", icon: "vendor" },
  { title: "Invoice #4821 — NCBA", when: "May 18", amount: "$260K", icon: "invoice" },
];

export const TOP_EXPENSES: {
  name: string;
  amount: string;
  category: "Payroll" | "Operations" | "Marketing" | "R&D";
}[] = [
  { name: "May Payroll", amount: "$1.84M", category: "Payroll" },
  { name: "Cloud Infrastructure", amount: "$142K", category: "Operations" },
  { name: "Q2 Campaign — Paid Media", amount: "$118K", category: "Marketing" },
  { name: "Contractor — Platform Team", amount: "$86K", category: "R&D" },
  { name: "Office & Facilities", amount: "$54K", category: "Operations" },
];

export const AI_RECS: { tone: "rose" | "amber" | "cyan"; text: string }[] = [
  { tone: "rose", text: "3 departments are within 5% of their budget ceiling." },
  { tone: "amber", text: "$420K VAT remittance due in 4 days — confirm cash cover." },
  { tone: "cyan", text: "Cash runway is 14 months at the current burn rate." },
  { tone: "cyan", text: "Net margin up 3.2pts YoY — reinvest into R&D." },
];

export const QUICK_ACTIONS: {
  label: string;
  icon: "invoice" | "expense" | "report" | "forecast";
}[] = [
  { label: "New Invoice", icon: "invoice" },
  { label: "Log Expense", icon: "expense" },
  { label: "Generate Report", icon: "report" },
  { label: "Cash Forecast", icon: "forecast" },
];
