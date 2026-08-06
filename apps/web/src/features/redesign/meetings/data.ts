// All sample — this page has no backend source yet. Every consumer wraps its
// section in a SampleTag (hidden under global Demo mode).

const NAMES = [
  "Abhishek K.",
  "Meera S.",
  "David M.",
  "Priya N.",
  "Rakesh P.",
  "Aarav K.",
  "Neha T.",
  "Suresh B.",
  "Vikram R.",
];

export const KPIS: {
  label: string;
  value: string;
  delta?: number;
  deltaSuffix?: string;
  sub: string;
  icon: "today" | "week" | "hours" | "actions" | "attendance";
}[] = [
  {
    label: "Today's Meetings",
    value: "5",
    delta: 2,
    deltaSuffix: "",
    sub: "vs yesterday",
    icon: "today",
  },
  { label: "This Week", value: "18", delta: 12, sub: "vs last week", icon: "week" },
  { label: "Meeting Hours", value: "12.4h", delta: -8, sub: "vs last week", icon: "hours" },
  {
    label: "Action Items",
    value: "23",
    delta: 5,
    deltaSuffix: "",
    sub: "new today",
    icon: "actions",
  },
  { label: "Attendance Rate", value: "96%", delta: 4, sub: "vs last week", icon: "attendance" },
];

export type SlotColor = "rose" | "cyan" | "violet" | "green" | "amber";

export interface CalSlot {
  time: string;
  title: string;
  range?: string;
  color: SlotColor;
  allDay?: boolean;
  priority?: string;
  attendees?: string[];
  extra?: number;
  now?: boolean; // render the "now" indicator after this slot
}

export const DAY_LABEL = "May 7, 2025";
export const CAL_SLOTS: CalSlot[] = [
  {
    time: "All Day",
    title: "Bidco Implementation Review",
    color: "rose",
    allDay: true,
    priority: "High Priority",
  },
  {
    time: "09:00 AM",
    title: "Executive Leadership Standup",
    range: "09:00 – 09:30 AM",
    color: "cyan",
    attendees: NAMES.slice(0, 3),
    extra: 5,
  },
  {
    time: "10:00 AM",
    title: "Bidco Project Steering Committee",
    range: "10:00 – 11:30 AM",
    color: "violet",
    attendees: NAMES.slice(2, 5),
    extra: 8,
    now: true,
  },
  {
    time: "12:00 PM",
    title: "Finance Review & Cash Flow Update",
    range: "12:00 – 01:00 PM",
    color: "green",
    attendees: NAMES.slice(1, 4),
    extra: 3,
  },
  {
    time: "02:00 PM",
    title: "Product Roadmap Review",
    range: "02:00 – 03:00 PM",
    color: "amber",
    attendees: NAMES.slice(3, 6),
    extra: 4,
  },
  {
    time: "03:30 PM",
    title: "Marketing Strategy Sync",
    range: "03:30 – 04:30 PM",
    color: "cyan",
    attendees: NAMES.slice(0, 3),
    extra: 4,
  },
  {
    time: "05:00 PM",
    title: "AI Strategy & Innovation Review",
    range: "05:00 – 06:00 PM",
    color: "violet",
    attendees: NAMES.slice(4, 7),
    extra: 3,
  },
];

export type TagColor = "cyan" | "violet" | "green" | "amber";

export interface Upcoming {
  name: string;
  team: string;
  date: string;
  time: string;
  location: string;
  tag: string;
  tagColor: TagColor;
  attendees: string[];
  extra: number;
  icon: "board" | "platform" | "sales" | "hr" | "budget" | "success";
}

export const UPCOMING: Upcoming[] = [
  {
    name: "Board Meeting – Q2 2025",
    team: "Board of Directors",
    date: "May 09, 2025",
    time: "09:00 – 11:00 AM",
    location: "Nairobi HQ / Boardroom",
    tag: "Strategic",
    tagColor: "cyan",
    attendees: NAMES.slice(0, 5),
    extra: 6,
    icon: "board",
  },
  {
    name: "Neo Platform Review",
    team: "Product & Technology",
    date: "May 09, 2025",
    time: "02:00 – 03:30 PM",
    location: "Virtual Meeting",
    tag: "Review",
    tagColor: "cyan",
    attendees: NAMES.slice(1, 6),
    extra: 7,
    icon: "platform",
  },
  {
    name: "Sales Performance Review",
    team: "Sales Leadership Team",
    date: "May 10, 2025",
    time: "11:00 AM – 12:30 PM",
    location: "Virtual Meeting",
    tag: "Performance",
    tagColor: "green",
    attendees: NAMES.slice(2, 7),
    extra: 5,
    icon: "sales",
  },
  {
    name: "HR Monthly Review",
    team: "HR Leadership Team",
    date: "May 12, 2025",
    time: "10:00 – 11:30 AM",
    location: "Nairobi HQ / Room 3B",
    tag: "Review",
    tagColor: "cyan",
    attendees: NAMES.slice(0, 4),
    extra: 4,
    icon: "hr",
  },
  {
    name: "Q2 Budget Planning",
    team: "Finance & Leadership",
    date: "May 13, 2025",
    time: "01:00 – 03:00 PM",
    location: "Virtual Meeting",
    tag: "Planning",
    tagColor: "amber",
    attendees: NAMES.slice(3, 8),
    extra: 6,
    icon: "budget",
  },
  {
    name: "Customer Success Review",
    team: "Customer Success Team",
    date: "May 13, 2025",
    time: "04:00 – 05:00 PM",
    location: "Virtual Meeting",
    tag: "Review",
    tagColor: "cyan",
    attendees: NAMES.slice(1, 5),
    extra: 3,
    icon: "success",
  },
];

export const NEXT_MEETING = {
  in: "in 36m",
  title: "Bidco Project Steering Committee",
  time: "10:00 – 11:30 AM (1h 30m)",
  location: "Nairobi HQ / Boardroom",
  attendees: NAMES.slice(0, 5),
  extra: 8,
  agenda: [
    "Project status update",
    "Timeline & milestones",
    "Risks & issues",
    "Resource allocation",
    "Next steps",
  ],
};

export type Priority = "High" | "Medium" | "Low";

export const TASKS: { title: string; context: string; due: string; priority: Priority }[] = [
  {
    title: "Review HR Genie UAT results",
    context: "Bidco Steering Committee",
    due: "Due Today",
    priority: "High",
  },
  {
    title: "Approve Q2 marketing budget",
    context: "Marketing Strategy Sync",
    due: "Due Tomorrow",
    priority: "Medium",
  },
  {
    title: "Update cash flow projections",
    context: "Finance Review",
    due: "Due May 9",
    priority: "High",
  },
  {
    title: "Provide feedback on roadmap",
    context: "Product Roadmap Review",
    due: "Due May 9",
    priority: "Low",
  },
];

export const PRIORITY_PILL: Record<Priority, string> = {
  High: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  Medium: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  Low: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
};

export const QUICK_ACTIONS: {
  label: string;
  icon: "schedule" | "instant" | "notes" | "summary" | "report" | "templates";
}[] = [
  { label: "Schedule Meeting", icon: "schedule" },
  { label: "Start Instant Meeting", icon: "instant" },
  { label: "Meeting Notes", icon: "notes" },
  { label: "AI Meeting Summary", icon: "summary" },
  { label: "Action Items Report", icon: "report" },
  { label: "Meeting Templates", icon: "templates" },
];

const UP1 = [4, 6, 5, 7, 6, 9, 8, 11, 10, 13, 12, 15];
const UP2 = [10, 14, 12, 18, 16, 22, 26, 24, 30, 34, 40, 46];
const UP3 = [20, 22, 21, 24, 26, 25, 29, 31, 30, 34, 36, 40];

export const INSIGHTS: {
  title: string;
  value: string;
  sub: string;
  delta?: number;
  chart: "spark-green" | "bars-violet" | "ring" | "spark-amber";
  data: number[];
  ringPct?: number;
}[] = [
  {
    title: "You have 18 meetings this week",
    value: "18",
    sub: "more than last week",
    delta: 12,
    chart: "spark-green",
    data: UP1,
  },
  {
    title: "Most productive time",
    value: "10:00 AM – 12:00 PM",
    sub: "78% meeting effectiveness",
    chart: "bars-violet",
    data: UP2,
  },
  {
    title: "Action items completion",
    value: "87% completed",
    sub: "vs last week",
    delta: 9,
    chart: "ring",
    data: [],
    ringPct: 87,
  },
  {
    title: "Focus time lost",
    value: "3.2 hours this week",
    sub: "vs last week",
    delta: -15,
    chart: "spark-amber",
    data: UP3,
  },
];
