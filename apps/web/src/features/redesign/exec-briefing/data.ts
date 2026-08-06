import type { LineTrendPoint, SparkColor } from "@/features/redesign/components";

// All values below are placeholder — no live endpoint. Consumers render a
// SampleTag. Real signals (projects health/counts) come from useDashboardData.

const up = [10, 13, 12, 17, 16, 21, 24, 23, 28, 31, 34, 40];
const up2 = [8, 12, 11, 15, 19, 18, 24, 28, 31, 35, 39, 46];
const down = [40, 38, 39, 35, 33, 30, 31, 27, 25, 24, 22, 20];
const bars = [8, 12, 6, 14, 10, 16, 9, 18, 13, 20, 15, 22];

export const EFFICIENCY_TREND: LineTrendPoint[] = [
  { label: "1 May", value: 58 },
  { label: "2 May", value: 66 },
  { label: "3 May", value: 61 },
  { label: "4 May", value: 74 },
  { label: "5 May", value: 70 },
  { label: "6 May", value: 82 },
  { label: "7 May", value: 88 },
];

export const REGIONS: { name: string; role: string; percent: number; side: "left" | "right" }[] = [
  { name: "Kenya", role: "Operations", percent: 98, side: "left" },
  { name: "UAE", role: "Sales", percent: 92, side: "left" },
  { name: "Remote", role: "Workforce", percent: 94, side: "left" },
  { name: "India", role: "Development", percent: 96, side: "right" },
  { name: "Rwanda", role: "Projects", percent: 88, side: "right" },
  { name: "Global", role: "Clients", percent: 97, side: "right" },
];

export const SNAPSHOT: {
  label: string;
  value: string;
  delta: number;
  deltaSuffix?: string;
  color: SparkColor;
  trend: number[];
  bars?: boolean;
}[] = [
  { label: "Revenue", value: "$1.24M", delta: 18.6, color: "cyan", trend: up },
  { label: "Sales Growth", value: "$7.82M", delta: 24.7, color: "violet", trend: up2 },
  { label: "Cash Flow", value: "$2.54M", delta: 8.3, color: "green", trend: up },
  { label: "Projects Health", value: "85%", delta: 6, color: "cyan", trend: up },
  {
    label: "Employees",
    value: "156",
    delta: 12,
    deltaSuffix: "",
    color: "amber",
    trend: bars,
    bars: true,
  },
  { label: "CSAT Score", value: "4.8/5", delta: 0.6, deltaSuffix: "", color: "green", trend: up },
  { label: "AI Usage", value: "78%", delta: 15, color: "violet", trend: up2 },
  { label: "Burn Rate", value: "$120K/mo", delta: -5, color: "rose", trend: down },
];

export const MEETINGS: { title: string; time: string; badge: string; now?: boolean }[] = [
  { title: "Bidco Steering Committee", time: "09:30 AM - 10:30 AM", badge: "NOW", now: true },
  { title: "Executive Strategy Call", time: "11:00 AM - 12:00 PM", badge: "2h" },
  { title: "HR Genie Review", time: "02:00 PM - 03:00 PM", badge: "5h" },
  { title: "Board Meeting Prep", time: "04:00 PM - 05:00 PM", badge: "7h" },
];

export const ALERTS: { severity: "HIGH" | "MEDIUM" | "LOW"; title: string; meta: string }[] = [
  { severity: "HIGH", title: "Bidco project delay risk", meta: "High probability" },
  { severity: "MEDIUM", title: "Server utilization high", meta: "Production cluster" },
  { severity: "MEDIUM", title: "2 employees require attention", meta: "Performance issue" },
];

export const RECOMMENDATIONS: { title: string; sub: string }[] = [
  { title: "Approve budget for Bidco phase 2", sub: "Estimated impact: +18% efficiency" },
  { title: "Review pricing strategy", sub: "for HR Genie Enterprise" },
  { title: "Consider expanding", sub: "into East African market" },
];
