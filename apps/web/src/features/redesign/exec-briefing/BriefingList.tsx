import {
  AlertTriangle,
  CalendarDays,
  ChevronRight,
  ClipboardCheck,
  DollarSign,
  FolderKanban,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { Delta, GlowCard } from "@/features/redesign/components";
import { round } from "@/features/redesign/components/format";
import { SectionSampleChip } from "./DemoMode";

type StatusTone = "good" | "excellent" | "attention" | "high" | "action" | "on-track" | "new";

const STATUS: Record<StatusTone, { label: string; cls: string }> = {
  good: { label: "Good", cls: "border-rd-green/40 bg-rd-green/10 text-rd-green" },
  excellent: { label: "Excellent", cls: "border-rd-green/40 bg-rd-green/10 text-rd-green" },
  attention: { label: "Attention", cls: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber" },
  high: { label: "High", cls: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose" },
  action: { label: "Action Required", cls: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose" },
  "on-track": { label: "On Track", cls: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan" },
  new: { label: "New", cls: "border-rd-violet/40 bg-rd-violet/10 text-rd-violet" },
};

interface Row {
  icon: LucideIcon;
  label: string;
  subtext: string;
  status: StatusTone;
  value: string;
  delta?: number;
  real?: boolean;
}

interface Props {
  projectsHealth: number | null;
  counts: { onTrack: number; atRisk: number; delayed: number };
  overviewsReady: boolean;
}

export function BriefingList({ projectsHealth, counts, overviewsReady }: Props) {
  const projectsReal = overviewsReady && projectsHealth != null;
  const projectsSub = projectsReal
    ? `${counts.onTrack} on track, ${counts.atRisk} at risk, ${counts.delayed} delayed`
    : "3 projects on track, 1 at risk, 1 delayed";

  const rows: Row[] = [
    {
      icon: TrendingUp,
      label: "Revenue",
      subtext: "Total revenue is up 18.6% compared to last month.",
      status: "good",
      value: "$1.24M",
      delta: 18.6,
    },
    {
      icon: Wallet,
      label: "Cash Position",
      subtext: "Cash position is healthy and covers 7.2 months of expenses.",
      status: "good",
      value: "$2.54M",
      delta: 8.3,
    },
    {
      icon: DollarSign,
      label: "Sales Pipeline",
      subtext: "Strong pipeline growth across all companies.",
      status: "excellent",
      value: "$7.82M",
      delta: 24.7,
    },
    {
      icon: FolderKanban,
      label: "Projects",
      subtext: projectsSub,
      status: "attention",
      value: `${round(projectsReal ? Math.round(projectsHealth) : 85)}%`,
      delta: 6,
      real: projectsReal,
    },
    {
      icon: AlertTriangle,
      label: "Critical Risks",
      subtext: "2 high risks require immediate attention.",
      status: "high",
      value: "2",
    },
    {
      icon: ClipboardCheck,
      label: "Pending Decisions",
      subtext: "7 decisions are waiting for your approval.",
      status: "action",
      value: "7",
    },
    {
      icon: CalendarDays,
      label: "Today's Meetings",
      subtext: "4 meetings scheduled today.",
      status: "on-track",
      value: "4",
    },
    {
      icon: Target,
      label: "CEO Priorities",
      subtext: "8 priorities in progress.",
      status: "on-track",
      value: "8",
    },
    {
      icon: Sparkles,
      label: "AI Recommendations",
      subtext: "5 new AI recommendations for you.",
      status: "new",
      value: "5",
    },
  ];

  return (
    <GlowCard className="p-0">
      <div className="flex items-center justify-between gap-2 border-b border-rd-border px-5 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-rd-heading">
          Today&apos;s Executive Briefing
        </h2>
        <SectionSampleChip />
      </div>
      <div className="px-5">
        {rows.map((r) => {
          const Icon = r.icon;
          const st = STATUS[r.status];
          return (
            <div
              key={r.label}
              className="flex items-center gap-3 border-b border-rd-border py-3 last:border-b-0"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control border border-rd-border bg-rd-panel text-rd-cyan">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{r.label}</p>
                <p className="truncate text-xs text-rd-muted">{r.subtext}</p>
              </div>
              <span
                className={cn(
                  "hidden shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium lg:inline-block",
                  st.cls,
                )}
              >
                {st.label}
              </span>
              <div className="flex w-20 shrink-0 flex-col items-end leading-tight">
                <span className="text-sm font-semibold tabular-nums text-rd-heading">
                  {r.value}
                </span>
                {r.delta !== undefined && <Delta value={r.delta} />}
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-rd-muted" aria-hidden />
            </div>
          );
        })}
      </div>
    </GlowCard>
  );
}
