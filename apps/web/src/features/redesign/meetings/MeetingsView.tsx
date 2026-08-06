"use client";

import {
  Calendar,
  CalendarDays,
  CheckCircle2,
  Clock,
  GanttChartSquare,
  Plus,
  Users,
  Video,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { Delta, SampleTag } from "@/features/redesign/components";
import { DayCalendar } from "./DayCalendar";
import { MeetingInsights } from "./MeetingInsights";
import { MeetingsRightRail } from "./MeetingsRightRail";
import { UpcomingList } from "./UpcomingList";
import { KPIS } from "./data";

const KPI_ICON: Record<string, LucideIcon> = {
  today: Calendar,
  week: CalendarDays,
  hours: Clock,
  actions: CheckCircle2,
  attendance: Users,
};

export function MeetingsView() {
  const [view, setView] = useState<"calendar" | "timeline">("calendar");

  return (
    <div className="mx-auto max-w-[1700px] space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="h-7 w-1 rounded-full bg-rd-grad" aria-hidden />
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-rd-heading">
              Meetings
              <Video className="h-5 w-5 text-rd-muted" aria-hidden />
            </h1>
            <p className="mt-0.5 text-sm text-rd-body">
              Manage your schedule. Run smarter meetings. Get things done.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-control border border-rd-border bg-rd-panel/50 p-0.5">
            <SegBtn
              active={view === "calendar"}
              onClick={() => setView("calendar")}
              icon={Calendar}
              label="Calendar"
            />
            <SegBtn
              active={view === "timeline"}
              onClick={() => setView("timeline")}
              icon={GanttChartSquare}
              label="Timeline"
            />
          </div>
          <button
            type="button"
            className="flex items-center gap-2 rounded-control bg-rd-grad px-3.5 py-2 text-sm font-medium text-white"
          >
            <Plus className="h-4 w-4" aria-hidden />
            New Meeting
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {KPIS.map((k) => {
          const Icon = KPI_ICON[k.icon];
          return (
            <div key={k.label} className="glow-card p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <SampleTag />
              </div>
              <p className="mt-3 text-xs uppercase tracking-wide text-rd-muted">{k.label}</p>
              <p className="mt-0.5 text-2xl font-semibold tabular-nums text-rd-heading">
                {k.value}
              </p>
              <div className="mt-0.5 flex items-center gap-1.5">
                {k.delta !== undefined && <Delta value={k.delta} suffix={k.deltaSuffix ?? "%"} />}
                <span className="text-xs text-rd-muted">{k.sub}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main: day calendar | upcoming | right rail */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-[340px_minmax(0,1fr)_340px]">
        <DayCalendar />
        <UpcomingList />
        <div className="lg:col-span-2 xl:col-span-1">
          <MeetingsRightRail />
        </div>
      </div>

      {/* Bottom insights */}
      <MeetingInsights />
    </div>
  );
}

function SegBtn({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active ? "bg-rd-grad text-white" : "text-rd-muted hover:text-rd-heading",
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
      {label}
    </button>
  );
}
