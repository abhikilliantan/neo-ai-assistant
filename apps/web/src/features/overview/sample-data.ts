// PLACEHOLDER content for the Team table + Activity feed. These surfaces have no
// backend wiring yet (Team / Activity slices are unbuilt), so the rows below are
// illustrative sample data — the UI labels them "Sample" so they are never
// mistaken for live figures. Delete this file when those slices land.

export type TeamMember = {
  name: string;
  role: string; // "HOD" or "—"
  department: string;
  task: string;
  project: string;
  status: "On track" | "Blocked";
};

export const SAMPLE_TEAM: TeamMember[] = [
  {
    name: "Priya Nair",
    role: "HOD",
    department: "Marketing",
    task: "LinkedIn campaign calendar",
    project: "LinkedIn Content Engine",
    status: "On track",
  },
  {
    name: "Arjun Menon",
    role: "HOD",
    department: "Sales",
    task: "Enterprise pipeline review",
    project: "Sales Pipeline CRM",
    status: "On track",
  },
  {
    name: "Suresh B.",
    role: "HOD",
    department: "Development",
    task: "Bidco Phase 2 – Integrations",
    project: "Bidco HR Genie Delivery",
    status: "Blocked",
  },
  {
    name: "Neha Sharma",
    role: "HOD",
    department: "QA",
    task: "Test cases – Payroll module",
    project: "Bidco Test Cycle",
    status: "On track",
  },
  {
    name: "Anita Verma",
    role: "HOD",
    department: "People / HR",
    task: "Hiring plan & onboarding",
    project: "HR Operations",
    status: "Blocked",
  },
  {
    name: "Rohit K.",
    role: "—",
    department: "Development",
    task: "Fix: Leave module bug",
    project: "HR Genie Platform",
    status: "Blocked",
  },
  {
    name: "Karan J.",
    role: "—",
    department: "Development",
    task: "Neo dashboard – reports",
    project: "Neo Command Center",
    status: "On track",
  },
];

export type ActivityItem = {
  time: string;
  kind: "metric" | "schedule" | "blocked" | "done" | "people" | "report";
  title: string;
  meta: string;
};

export const SAMPLE_ACTIVITY: ActivityItem[] = [
  {
    time: "9:42 AM",
    kind: "metric",
    title: "Bidco open actions 71 → 74 (+3)",
    meta: "Development • By Neo AI",
  },
  {
    time: "9:15 AM",
    kind: "schedule",
    title: "LinkedIn Wed/Thu/Fri scheduled 6 AM",
    meta: "Marketing • By Neo AI",
  },
  {
    time: "8:50 AM",
    kind: "blocked",
    title: "Blocked: Bidco Phase 2 – Integrations",
    meta: "Suresh B. • Development",
  },
  {
    time: "8:30 AM",
    kind: "done",
    title: "Payroll module test cycle 60% → 75%",
    meta: "QA • By Neha Sharma",
  },
  {
    time: "8:10 AM",
    kind: "people",
    title: "Anita Verma added to Hiring plan",
    meta: "People / HR • By Neo AI",
  },
  { time: "7:45 AM", kind: "report", title: "Weekly report generated", meta: "Neo AI • Auto" },
];
