// All sample — Neo has no marketing/campaign backend yet. Every section carries
// a SampleTag (hidden under global Demo mode). Values mirror the Marketing
// Command Center mockup.

import type { FunnelRow } from "@/features/redesign/components";

export const CHIPS = [
  "What's our marketing ROI this month?",
  "Which campaign is performing best?",
  "Show website conversion trend",
  "Top content by engagement",
];

const SP_SPEND = [140, 136, 138, 132, 134, 130, 128, 126, 130, 127, 129, 128];
const SP_LEADS = [18, 20, 19, 22, 24, 23, 26, 25, 27, 26, 28, 28];
const SP_QUAL = [6, 7, 6, 8, 7, 9, 8, 9, 10, 9, 10, 9];
const SP_CONV = [40, 42, 41, 44, 43, 45, 44, 46, 45, 47, 46, 46];
const SP_ROI = [28, 30, 29, 32, 34, 33, 35, 34, 36, 35, 37, 38];
const SP_PIPE = [18, 19, 20, 21, 20, 22, 21, 23, 22, 23, 23, 23];

export interface MktKpi {
  label: string;
  value: string;
  delta: number;
  deltaSuffix?: string;
  sub: string;
  icon: "spend" | "leads" | "qualified" | "conversion" | "roi" | "pipeline";
  color: "cyan" | "violet" | "green" | "amber" | "rose";
  spark: number[];
}

export const KPIS: MktKpi[] = [
  {
    label: "Total Marketing Spend (MTD)",
    value: "$128.4K",
    delta: -8.6,
    sub: "vs last month",
    icon: "spend",
    color: "cyan",
    spark: SP_SPEND,
  },
  {
    label: "Total Leads (MTD)",
    value: "2,847",
    delta: 24.3,
    sub: "vs last month",
    icon: "leads",
    color: "violet",
    spark: SP_LEADS,
  },
  {
    label: "Qualified Leads (MTD)",
    value: "942",
    delta: 18.7,
    sub: "vs last month",
    icon: "qualified",
    color: "green",
    spark: SP_QUAL,
  },
  {
    label: "Conversion Rate (MTD)",
    value: "4.62%",
    delta: 0.8,
    deltaSuffix: "pp",
    sub: "vs last month",
    icon: "conversion",
    color: "amber",
    spark: SP_CONV,
  },
  {
    label: "Marketing ROI (MTD)",
    value: "380%",
    delta: 35.2,
    sub: "vs last month",
    icon: "roi",
    color: "violet",
    spark: SP_ROI,
  },
  {
    label: "Pipeline Influenced",
    value: "$2.34M",
    delta: 25.6,
    sub: "vs last month",
    icon: "pipeline",
    color: "cyan",
    spark: SP_PIPE,
  },
];

export interface ChannelRow {
  name: string;
  icon: "linkedin" | "website" | "email" | "search" | "youtube" | "webinar" | "events";
  visitors: string;
  leads: string;
  convRate: string;
  roi: number; // %
  spark: number[];
}

export const CHANNELS: ChannelRow[] = [
  {
    name: "LinkedIn",
    icon: "linkedin",
    visitors: "12,842",
    leads: "642",
    convRate: "5.01%",
    roi: 422,
    spark: [30, 34, 32, 40, 44, 42, 50],
  },
  {
    name: "Website",
    icon: "website",
    visitors: "18,721",
    leads: "788",
    convRate: "4.21%",
    roi: 356,
    spark: [40, 42, 44, 43, 48, 52, 58],
  },
  {
    name: "Email Campaigns",
    icon: "email",
    visitors: "8,563",
    leads: "421",
    convRate: "4.91%",
    roi: 312,
    spark: [20, 24, 22, 26, 28, 27, 30],
  },
  {
    name: "Paid Search",
    icon: "search",
    visitors: "6,291",
    leads: "312",
    convRate: "4.96%",
    roi: 286,
    spark: [16, 18, 20, 19, 22, 24, 23],
  },
  {
    name: "YouTube",
    icon: "youtube",
    visitors: "4,827",
    leads: "183",
    convRate: "3.79%",
    roi: 241,
    spark: [10, 12, 11, 14, 13, 16, 18],
  },
  {
    name: "Webinars",
    icon: "webinar",
    visitors: "2,153",
    leads: "156",
    convRate: "7.24%",
    roi: 178,
    spark: [8, 9, 10, 12, 11, 13, 14],
  },
  {
    name: "Events",
    icon: "events",
    visitors: "1,256",
    leads: "98",
    convRate: "7.80%",
    roi: 612,
    spark: [12, 14, 16, 20, 24, 28, 34],
  },
];

// Leads Funnel (MTD)
export const FUNNEL: FunnelRow[] = [
  { label: "Visitors", value: "58,642", color: "hsl(var(--rd-cyan))" },
  { label: "Leads", value: "2,847", pct: "4.86%", color: "hsl(var(--rd-cyan-2))" },
  { label: "MQL", value: "1,256", pct: "44.1%", color: "hsl(var(--rd-violet))" },
  { label: "SQL", value: "942", pct: "75.0%", color: "hsl(var(--rd-amber))" },
  { label: "Opportunities", value: "612", pct: "64.9%", color: "hsl(var(--rd-violet-2))" },
  { label: "Customers", value: "134", pct: "21.9%", color: "hsl(var(--rd-green))" },
];
export const FUNNEL_OVERALL = "4.62%";

export interface CampaignRow {
  name: string;
  spend: string;
  leads: string;
  roi: number; // %
  spark: number[];
}

export const CAMPAIGNS: CampaignRow[] = [
  {
    name: "HR Genie Awareness",
    spend: "$32.4K",
    leads: "842",
    roi: 452,
    spark: [28, 32, 36, 40, 45],
  },
  {
    name: "LinkedIn Thought Leadership",
    spend: "$18.7K",
    leads: "521",
    roi: 388,
    spark: [24, 26, 30, 34, 38],
  },
  {
    name: "Webinar: Future of HR",
    spend: "$14.2K",
    leads: "312",
    roi: 592,
    spark: [30, 38, 44, 52, 59],
  },
  {
    name: "Google Search Ads",
    spend: "$19.8K",
    leads: "298",
    roi: 649,
    spark: [40, 46, 52, 60, 65],
  },
  {
    name: "Email Nurture Campaign",
    spend: "$8.6K",
    leads: "263",
    roi: 649,
    spark: [38, 44, 50, 58, 65],
  },
  {
    name: "Product Launch Campaign",
    spend: "$22.7K",
    leads: "451",
    roi: 549,
    spark: [32, 40, 46, 50, 55],
  },
  {
    name: "Re-engagement Campaign",
    spend: "$12.0K",
    leads: "160",
    roi: 312,
    spark: [18, 22, 26, 28, 31],
  },
];

// Traffic Overview — daily users
export const TRAFFIC: { label: string; users: number }[] = [
  { label: "May 1", users: 18200 },
  { label: "May 2", users: 21400 },
  { label: "May 3", users: 27600 },
  { label: "May 4", users: 24800 },
  { label: "May 5", users: 33200 },
  { label: "May 6", users: 41800 },
  { label: "May 7", users: 58642 },
];

export interface ContentRow {
  title: string;
  type: "Blog Post" | "LinkedIn Post" | "Video" | "Webinar" | "Case Study";
  engagement: string;
  delta: number;
}

export const TOP_CONTENT: ContentRow[] = [
  { title: "The Future of AI in HR", type: "Blog Post", engagement: "2,842", delta: 24 },
  {
    title: "10 Ways HR Automation Saves Time",
    type: "LinkedIn Post",
    engagement: "2,341",
    delta: 18,
  },
  { title: "HR Genie Product Overview", type: "Video", engagement: "1,982", delta: 31 },
  { title: "Webinar: Future of HR", type: "Webinar", engagement: "1,542", delta: 27 },
  { title: "Case Study: Bidco Implementation", type: "Case Study", engagement: "1,231", delta: 15 },
];

// Marketing ROI Over Time — monthly %
export const ROI_TREND: { label: string; roi: number }[] = [
  { label: "Apr", roi: 130 },
  { label: "May", roi: 175 },
  { label: "Jun", roi: 240 },
  { label: "Jul", roi: 280 },
  { label: "Aug", roi: 340 },
  { label: "Sep", roi: 410 },
  { label: "Oct", roi: 470 },
];

export const ACTIVITIES: {
  title: string;
  sub: string;
  when: string;
  icon: "blog" | "linkedin" | "email" | "youtube" | "ad";
}[] = [
  {
    title: "Blog Post Published",
    sub: "The Future of AI in HR",
    when: "Today, 9:30 AM",
    icon: "blog",
  },
  {
    title: "LinkedIn Post",
    sub: "AI in HR: 5 Trends Shaping 2025",
    when: "Today, 11:00 AM",
    icon: "linkedin",
  },
  {
    title: "Email Campaign Sent",
    sub: "HR Genie Webinar Invite",
    when: "Today, 2:15 PM",
    icon: "email",
  },
  {
    title: "YouTube Video Published",
    sub: "HR Automation Explained",
    when: "Yesterday, 4:30 PM",
    icon: "youtube",
  },
  {
    title: "Ad Campaign Launched",
    sub: "Google Search Campaign",
    when: "Yesterday, 10:00 AM",
    icon: "ad",
  },
];

export const TASKS: { label: string; due: string; priority: "High" | "Medium" | "Low" }[] = [
  { label: "Review Q2 Content Calendar", due: "Due Today", priority: "High" },
  { label: "Approve LinkedIn Ads", due: "Due Today", priority: "Medium" },
  { label: "Prepare Case Study – Bidco", due: "Due Tomorrow", priority: "High" },
  { label: "Analyze Webinar Performance", due: "Due May 10", priority: "Low" },
  { label: "Update Website Landing Page", due: "Due May 12", priority: "Medium" },
];

export const AI_RECS: { tone: "rose" | "amber" | "green" | "cyan"; text: string }[] = [
  { tone: "rose", text: "Increase budget for HR Genie Awareness campaign." },
  { tone: "amber", text: "Best time to post on LinkedIn is 9–11 AM." },
  { tone: "green", text: "Webinars generate 2.3x more qualified leads." },
  { tone: "cyan", text: "Consider launching retargeting ads for website visitors." },
];

export const QUICK_ACTIONS: {
  label: string;
  icon: "campaign" | "content" | "report" | "calendar";
}[] = [
  { label: "Create Campaign", icon: "campaign" },
  { label: "Write Content", icon: "content" },
  { label: "Generate Report", icon: "report" },
  { label: "Marketing Calendar", icon: "calendar" },
];
