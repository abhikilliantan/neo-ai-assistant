"use client";

import {
  BarChart3,
  ChevronDown,
  Crown,
  LayoutDashboard,
  PiggyBank,
  Smile,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { AvatarStack, SampleTag } from "@/features/redesign/components";
import { UPCOMING, type TagColor, type Upcoming } from "./data";

const ICONS: Record<Upcoming["icon"], LucideIcon> = {
  board: Crown,
  platform: LayoutDashboard,
  sales: BarChart3,
  hr: Users,
  budget: PiggyBank,
  success: Smile,
};

const TAG: Record<TagColor, string> = {
  cyan: "text-rd-cyan",
  violet: "text-rd-violet",
  green: "text-rd-green",
  amber: "text-rd-amber",
};

export function UpcomingList() {
  return (
    <div className="glow-card flex min-w-0 flex-col p-0">
      <div className="flex items-center justify-between gap-2 border-b border-rd-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-rd-heading">Upcoming Meetings</h2>
          <SampleTag />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="flex items-center gap-1 rounded-control border border-rd-border px-2.5 py-1 text-xs text-rd-body hover:text-rd-heading"
          >
            All Meetings
            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
          </button>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
      </div>

      <ul className="flex-1 divide-y divide-rd-border">
        {UPCOMING.map((m) => {
          const Icon = ICONS[m.icon];
          return (
            <li key={m.name} className="flex items-center gap-4 px-4 py-3.5">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{m.name}</p>
                <p className="truncate text-xs text-rd-muted">{m.team}</p>
              </div>
              <div className="hidden shrink-0 text-right sm:block">
                <p className="text-xs text-rd-body">{m.date}</p>
                <p className="text-xs font-medium text-rd-heading">{m.time}</p>
                <p className="text-xs text-rd-muted">{m.location}</p>
              </div>
              <div className="hidden w-40 shrink-0 flex-col items-end gap-1.5 lg:flex">
                <span className={cn("text-xs font-medium", TAG[m.tagColor])}>{m.tag}</span>
                <AvatarStack names={m.attendees} extra={m.extra} size={22} />
              </div>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        className="border-t border-rd-border py-3 text-center text-sm font-medium text-rd-cyan hover:bg-rd-panel/50"
      >
        View all meetings →
      </button>
    </div>
  );
}
