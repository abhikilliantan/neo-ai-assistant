// All sample — no HR backend yet. Every section carries a SampleTag (hidden
// under global Demo mode).

export const CHIPS = [
  "Who is on leave today?",
  "Show top performers",
  "Which teams need attention?",
  "Headcount by department",
  "New hires this month",
];

const SP1 = [8, 10, 9, 12, 11, 14, 13, 16, 15, 18, 20, 22];
const SP2 = [12, 14, 13, 16, 18, 17, 20, 22, 24, 23, 26, 28];
const SP3 = [4, 6, 5, 8, 7, 10, 9, 12, 11, 13, 12, 14];
const SP4 = [10, 9, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14];
const SP5 = [3, 4, 3, 5, 4, 6, 5, 4, 6, 5, 4, 2];
const SP6 = [18, 19, 20, 21, 20, 22, 23, 22, 24, 25, 26, 27];

export const KPIS: {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  sub: string;
  icon: "total" | "active" | "hires" | "leave" | "attrition" | "tenure";
  color: "cyan" | "green" | "violet" | "amber" | "rose";
  spark: number[];
}[] = [
  {
    label: "Total Employees",
    value: "256",
    delta: 12,
    deltaSuffix: "",
    sub: "this month",
    icon: "total",
    color: "cyan",
    spark: SP1,
  },
  {
    label: "Active Employees",
    value: "238",
    sub: "93.0% of total",
    icon: "active",
    color: "green",
    spark: SP2,
  },
  {
    label: "New Hires (MTD)",
    value: "14",
    delta: 27,
    sub: "vs last month",
    icon: "hires",
    color: "violet",
    spark: SP3,
  },
  {
    label: "On Leave",
    value: "18",
    sub: "7.0% of total",
    icon: "leave",
    color: "amber",
    spark: SP4,
  },
  {
    label: "Attrition (MTD)",
    value: "2",
    delta: -1.2,
    sub: "vs last month",
    icon: "attrition",
    color: "rose",
    spark: SP5,
  },
  {
    label: "Avg. Tenure",
    value: "2.4 Yrs",
    delta: 0.3,
    deltaSuffix: "",
    sub: "vs last month",
    icon: "tenure",
    color: "cyan",
    spark: SP6,
  },
];

export const HEADCOUNT = {
  total: "256",
  slices: [
    { label: "Development", value: 76, pct: "29.7%", color: "hsl(var(--rd-cyan))" },
    { label: "Implementation", value: 42, pct: "16.4%", color: "hsl(var(--rd-violet))" },
    { label: "Sales", value: 38, pct: "14.8%", color: "hsl(var(--rd-green))" },
    { label: "Marketing", value: 26, pct: "10.2%", color: "hsl(var(--rd-rose))" },
    { label: "Finance", value: 22, pct: "8.6%", color: "hsl(var(--rd-amber))" },
    { label: "HR", value: 18, pct: "7.0%", color: "hsl(var(--rd-cyan-2))" },
    { label: "IT Operations", value: 14, pct: "5.5%", color: "hsl(var(--rd-violet-2))" },
    { label: "Other", value: 20, pct: "7.8%", color: "hsl(var(--rd-muted))" },
  ],
};

export const ENGAGEMENT = {
  score: 87,
  delta: 6,
  bars: [
    { label: "Satisfaction", value: 88, color: "hsl(var(--rd-cyan))" },
    { label: "Work Environment", value: 84, color: "hsl(var(--rd-green))" },
    { label: "Growth Opportunities", value: 82, color: "hsl(var(--rd-violet))" },
    { label: "Leadership", value: 90, color: "hsl(var(--rd-cyan-2))" },
    { label: "Compensation", value: 78, color: "hsl(var(--rd-amber))" },
  ],
};

export const DIVERSITY = {
  index: 52,
  delta: 4,
  male: { value: 148, pct: "57.8%" },
  female: { value: 108, pct: "42.2%" },
  nationalities: [
    { flag: "🇰🇪", label: "Kenya", pct: "42%" },
    { flag: "🇮🇳", label: "India", pct: "28%" },
    { flag: "🇷🇼", label: "Rwanda", pct: "12%" },
    { flag: "🇦🇪", label: "UAE", pct: "6%" },
    { flag: "🌍", label: "Other", pct: "12%" },
  ],
};

export type Dept = "Development" | "Implementation" | "Sales" | "Marketing" | "Finance";
export const DEPT_TAG: Record<Dept, string> = {
  Development: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
  Implementation: "border-rd-violet/40 bg-rd-violet/10 text-rd-violet",
  Sales: "border-rd-green/40 bg-rd-green/10 text-rd-green",
  Marketing: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  Finance: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
};

export type EmpStatus = "Active" | "On Leave";

export interface Employee {
  name: string;
  email: string;
  department: Dept;
  designation: string;
  location: string;
  status: EmpStatus;
  performance: number;
  spark: number[];
  tenure: string;
}

const P1 = [80, 82, 81, 85, 84, 88, 90, 89, 92, 91, 93, 93];
const P2 = [70, 72, 74, 73, 78, 80, 82, 85, 84, 88, 89, 90];
const P3 = [82, 84, 83, 86, 88, 87, 90, 89, 91, 90, 92, 91];
const P4 = [78, 80, 79, 82, 84, 83, 85, 86, 88, 87, 88, 87];

export const EMPLOYEES: Employee[] = [
  {
    name: "Alex Kane",
    email: "alex.kane@skillmind.com",
    department: "Development",
    designation: "Senior Full Stack Engineer",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 93,
    spark: P1,
    tenure: "3.2 Yrs",
  },
  {
    name: "Meera Shah",
    email: "meera.shah@skillmind.com",
    department: "Implementation",
    designation: "Project Manager",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 90,
    spark: P3,
    tenure: "2.7 Yrs",
  },
  {
    name: "David Mwangi",
    email: "david.mwangi@skillmind.com",
    department: "Sales",
    designation: "Sales Director",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 91,
    spark: P3,
    tenure: "4.1 Yrs",
  },
  {
    name: "Priya Nair",
    email: "priya.nair@skillmind.com",
    department: "Finance",
    designation: "Finance Manager",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 87,
    spark: P4,
    tenure: "2.3 Yrs",
  },
  {
    name: "Rakesh Patel",
    email: "rakesh.patel@skillmind.com",
    department: "Development",
    designation: "DevOps Engineer",
    location: "Nairobi, Kenya",
    status: "On Leave",
    performance: 85,
    spark: P4,
    tenure: "1.8 Yrs",
  },
  {
    name: "Neha Tiwari",
    email: "neha.tiwari@skillmind.com",
    department: "Marketing",
    designation: "Marketing Lead",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 89,
    spark: P2,
    tenure: "2.1 Yrs",
  },
  {
    name: "Al Kane",
    email: "al.kane@skillmind.com",
    department: "Implementation",
    designation: "Implementation Specialist",
    location: "Nairobi, Kenya",
    status: "Active",
    performance: 92,
    spark: P1,
    tenure: "1.6 Yrs",
  },
];

export const SNAPSHOT: {
  label: string;
  count: number;
  icon: "cake" | "award" | "plane" | "userplus";
  people: string[];
}[] = [
  { label: "Birthdays", count: 3, icon: "cake", people: ["Alex Kane", "Meera Shah", "Priya Nair"] },
  {
    label: "Work Anniversaries",
    count: 5,
    icon: "award",
    people: ["David Mwangi", "Neha Tiwari", "Al Kane"],
  },
  {
    label: "On Leave Today",
    count: 6,
    icon: "plane",
    people: ["Rakesh Patel", "Suresh B.", "Vikram R."],
  },
  { label: "New Joiners", count: 2, icon: "userplus", people: ["Aarav K.", "Sana M."] },
];

export const TOP_PERFORMERS: { name: string; dept: string; pct: number }[] = [
  { name: "Alex Kane", dept: "Development", pct: 93 },
  { name: "David Mwangi", dept: "Sales", pct: 91 },
  { name: "Meera Shah", dept: "Implementation", pct: 90 },
  { name: "Priya Nair", dept: "Finance", pct: 87 },
  { name: "Neha Tiwari", dept: "Marketing", pct: 86 },
];

export const QUICK_ACTIONS: {
  label: string;
  icon: "add" | "report" | "review" | "org" | "import" | "export";
}[] = [
  { label: "Add Employee", icon: "add" },
  { label: "Employee Report", icon: "report" },
  { label: "Performance Review", icon: "review" },
  { label: "Org Chart", icon: "org" },
  { label: "Bulk Import", icon: "import" },
  { label: "Export Directory", icon: "export" },
];

export const AI_RECS: { tone: "cyan" | "amber" | "green"; text: string }[] = [
  { tone: "cyan", text: "2 high performers are eligible for promotion." },
  { tone: "amber", text: "Development department is over capacity." },
  { tone: "green", text: "Consider hiring 3 more in Sales team." },
];

export const DEPARTMENTS: Dept[] = [
  "Development",
  "Implementation",
  "Sales",
  "Marketing",
  "Finance",
];
export const LOCATIONS = ["Nairobi, Kenya"];
