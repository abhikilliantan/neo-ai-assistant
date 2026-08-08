// All sample — Neo has no HR/payroll backend yet. Every section carries a
// SampleTag (hidden under global Demo mode). Values mirror the HR Command
// Center mockup. Charts use the cyan→violet brand ramp ONLY.

import type { FunnelRow } from "@/features/redesign/components";

export const CHIPS = [
  "How is hiring going?",
  "Who is at flight risk?",
  "Headcount by department",
  "Open positions this quarter",
  "Engagement trend",
];

const SP_HEAD = [212, 218, 224, 228, 232, 236, 240, 244, 246, 250, 253, 256];
const SP_HIRE = [4, 6, 5, 8, 7, 10, 9, 12, 11, 13, 12, 14];
const SP_OPEN = [10, 11, 12, 14, 13, 15, 16, 15, 17, 16, 17, 18];
const SP_ATTR = [9, 9, 8, 8, 8, 7, 7, 7, 7, 6, 6, 6];
const SP_TTH = [34, 33, 32, 30, 29, 28, 27, 26, 26, 25, 24, 24];

export interface HrKpi {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  sub: string;
  icon: "head" | "hires" | "open" | "attrition" | "tth" | "engagement";
  color: "cyan" | "violet";
  spark?: number[];
  /** engagement tile renders a ring gauge instead of a sparkline */
  gauge?: number;
}

export const KPIS: HrKpi[] = [
  {
    label: "Total Headcount",
    value: "256",
    delta: 12,
    deltaSuffix: "",
    sub: "vs last month",
    icon: "head",
    color: "cyan",
    spark: SP_HEAD,
  },
  {
    label: "New Hires (MTD)",
    value: "14",
    delta: 27,
    sub: "vs last month",
    icon: "hires",
    color: "violet",
    spark: SP_HIRE,
  },
  {
    label: "Open Positions",
    value: "18",
    sub: "across 8 depts",
    icon: "open",
    color: "cyan",
    spark: SP_OPEN,
  },
  {
    label: "Attrition Rate",
    value: "6.4%",
    sub: "−1.2pt vs last qtr",
    icon: "attrition",
    color: "violet",
    spark: SP_ATTR,
  },
  {
    label: "Avg Time to Hire",
    value: "24d",
    sub: "−3d vs last qtr",
    icon: "tth",
    color: "cyan",
    spark: SP_TTH,
  },
  {
    label: "Employee Engagement",
    value: "84%",
    sub: "eNPS +42",
    icon: "engagement",
    color: "cyan",
    gauge: 84,
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

export const FUNNEL_RAMP = brandRamp(5);

// Recruitment funnel
export const RECRUITMENT: FunnelRow[] = [
  { label: "Applied", value: "1,240", pct: "100%", color: FUNNEL_RAMP[0] },
  { label: "Screened", value: "480", pct: "39%", color: FUNNEL_RAMP[1] },
  { label: "Interviewed", value: "210", pct: "17%", color: FUNNEL_RAMP[2] },
  { label: "Offered", value: "64", pct: "5.2%", color: FUNNEL_RAMP[3] },
  { label: "Hired", value: "38", pct: "3.1%", color: FUNNEL_RAMP[4] },
];

const DEPT_RAMP = brandRamp(5);

// Headcount by Department donut
export const HEADCOUNT: {
  label: string;
  value: number;
  pct: string;
  color: string;
}[] = [
  { label: "Engineering", value: 96, pct: "37.5%", color: DEPT_RAMP[0] },
  { label: "Sales", value: 54, pct: "21.1%", color: DEPT_RAMP[1] },
  { label: "Operations", value: 42, pct: "16.4%", color: DEPT_RAMP[2] },
  { label: "Product", value: 34, pct: "13.3%", color: DEPT_RAMP[3] },
  { label: "G&A", value: 30, pct: "11.7%", color: DEPT_RAMP[4] },
];
export const HEADCOUNT_TOTAL = "256";

// Headcount Trend — single line
export const HEAD_TREND: { label: string; headcount: number }[] = [
  { label: "Jan", headcount: 224 },
  { label: "Feb", headcount: 232 },
  { label: "Mar", headcount: 240 },
  { label: "Apr", headcount: 248 },
  { label: "May", headcount: 256 },
];

export interface DeptRow {
  name: string;
  headcount: number;
  attrition: string;
  engagement: string;
  score: number;
}

export const DEPTS: DeptRow[] = [
  { name: "Engineering", headcount: 96, attrition: "5.2%", engagement: "87%", score: 90 },
  { name: "Sales", headcount: 54, attrition: "9.8%", engagement: "79%", score: 76 },
  { name: "Operations", headcount: 42, attrition: "6.1%", engagement: "82%", score: 84 },
  { name: "Product", headcount: 34, attrition: "4.4%", engagement: "88%", score: 91 },
  { name: "G&A", headcount: 30, attrition: "5.9%", engagement: "83%", score: 85 },
];

export const LOCATIONS: { label: string; value: string; delta: number }[] = [
  { label: "Nairobi", value: "128", delta: 8 },
  { label: "Mombasa", value: "42", delta: 5 },
  { label: "Kampala", value: "34", delta: 12 },
  { label: "Remote", value: "38", delta: 22 },
  { label: "Other", value: "14", delta: -4 },
];

// Workforce Health — distribution recolored to the cyan→violet ramp (semantic
// red/amber stays only on AI-recommendation alert icons).
const HEALTH_RAMP = brandRamp(4);

export const WORKFORCE_HEALTH: {
  total: string;
  slices: { label: string; count: number; pct: string; color: string }[];
  insight: string;
} = {
  total: "256",
  slices: [
    { label: "Thriving", count: 148, pct: "57.8%", color: HEALTH_RAMP[0] },
    { label: "Stable", count: 74, pct: "28.9%", color: HEALTH_RAMP[1] },
    { label: "At Risk", count: 22, pct: "8.6%", color: HEALTH_RAMP[2] },
    { label: "Flight Risk", count: 12, pct: "4.7%", color: HEALTH_RAMP[3] },
  ],
  insight:
    "12 employees show flight-risk signals — 7 are in Sales. Schedule retention 1:1s this week.",
};

export const UPCOMING: {
  title: string;
  when: string;
  icon: "interview" | "review" | "onboard" | "oneonone";
  people: string[];
  extra: number;
}[] = [
  {
    title: "Interview — Sr. Backend Eng",
    when: "Today, 11:00 AM",
    icon: "interview",
    people: ["Ada N.", "Ben O."],
    extra: 1,
  },
  {
    title: "Q2 Performance Reviews",
    when: "Today, 2:00 PM",
    icon: "review",
    people: ["Cara P.", "Dan Q.", "Eve R."],
    extra: 5,
  },
  {
    title: "Onboarding — 3 New Hires",
    when: "Tomorrow, 9:00 AM",
    icon: "onboard",
    people: ["Fay S.", "Gus T.", "Hana U."],
    extra: 0,
  },
  {
    title: "Retention 1:1 — Sales",
    when: "May 10, 10:30 AM",
    icon: "oneonone",
    people: ["Ivy V.", "Jack W."],
    extra: 2,
  },
];

export const OPEN_ROLES: {
  role: string;
  dept: string;
  priority: "High" | "Medium" | "Low";
}[] = [
  { role: "Sr. Backend Engineer", dept: "Engineering", priority: "High" },
  { role: "Enterprise Account Executive", dept: "Sales", priority: "High" },
  { role: "Product Designer", dept: "Product", priority: "Medium" },
  { role: "Implementation Lead", dept: "Operations", priority: "Medium" },
  { role: "People Ops Partner", dept: "G&A", priority: "Low" },
];

export const AI_RECS: { tone: "rose" | "amber" | "cyan"; text: string }[] = [
  { tone: "rose", text: "Sales attrition (9.8%) is 3.4pt above company average." },
  { tone: "amber", text: "12 employees flagged flight-risk — prioritize retention 1:1s." },
  { tone: "cyan", text: "2 offers pending >5 days — follow up to protect acceptance rate." },
  { tone: "cyan", text: "Engagement up 4pt QoQ — reinforce what's working in Product." },
];

export const QUICK_ACTIONS: {
  label: string;
  icon: "add" | "post" | "payroll" | "report";
}[] = [
  { label: "Add Employee", icon: "add" },
  { label: "Post Job", icon: "post" },
  { label: "Run Payroll", icon: "payroll" },
  { label: "Generate Report", icon: "report" },
];
