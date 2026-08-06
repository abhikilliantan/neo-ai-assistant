"use client";

import {
  CalendarPlus,
  ClipboardList,
  FileText,
  LayoutTemplate,
  MapPin,
  MoreHorizontal,
  Plus,
  Sparkles,
  Users,
  Video,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { SampleTag } from "@/features/redesign/components";
import { AvatarStack } from "./AvatarStack";
import { NEXT_MEETING, PRIORITY_PILL, QUICK_ACTIONS, TASKS } from "./data";

const QA_ICON: Record<string, LucideIcon> = {
  schedule: CalendarPlus,
  instant: Video,
  notes: FileText,
  summary: Sparkles,
  report: ClipboardList,
  templates: LayoutTemplate,
};

export function MeetingsRightRail() {
  return (
    <div className="space-y-4">
      {/* Next Meeting */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Next Meeting</h3>
            <SampleTag />
          </div>
          <span className="inline-flex items-center gap-1 text-xs font-medium text-rd-green">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rd-green" aria-hidden />
            {NEXT_MEETING.in}
          </span>
        </div>

        <div className="rounded-control border border-rd-border bg-rd-panel/40 p-3">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-rd-grad text-white">
              <Users className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-rd-heading">{NEXT_MEETING.title}</p>
              <p className="mt-0.5 text-xs text-rd-muted">{NEXT_MEETING.time}</p>
              <p className="mt-0.5 flex items-center gap-1 text-xs text-rd-muted">
                <MapPin className="h-3 w-3" aria-hidden />
                {NEXT_MEETING.location}
              </p>
            </div>
          </div>
          <div className="mt-3">
            <AvatarStack names={NEXT_MEETING.attendees} extra={NEXT_MEETING.extra} size={24} />
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              className="flex flex-1 items-center justify-center gap-2 rounded-control bg-rd-grad py-2.5 text-sm font-medium text-white"
            >
              <Video className="h-4 w-4" aria-hidden />
              Join Meeting
            </button>
            <button
              type="button"
              aria-label="More options"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control border border-rd-border text-rd-muted hover:text-rd-heading"
            >
              <MoreHorizontal className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>

        <div className="mt-4">
          <p className="mb-2 text-sm font-semibold text-rd-heading">Meeting agenda</p>
          <ol className="space-y-1.5">
            {NEXT_MEETING.agenda.map((a, i) => (
              <li key={a} className="flex items-start gap-2 text-sm text-rd-body">
                <span className="tabular-nums text-rd-muted">{i + 1}.</span>
                {a}
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* My Tasks from Meetings */}
      <div className="glow-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">My Tasks from Meetings</h3>
            <SampleTag />
          </div>
          <span className="text-xs font-medium text-rd-cyan">View all</span>
        </div>
        <ul className="space-y-3">
          {TASKS.map((t) => (
            <li key={t.title} className="flex items-start gap-2.5">
              <span
                className="mt-0.5 h-4 w-4 shrink-0 rounded border border-rd-border"
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{t.title}</p>
                <p className="truncate text-xs text-rd-muted">{t.context}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <span className="text-xs text-rd-body">{t.due}</span>
                <span
                  className={cn(
                    "rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                    PRIORITY_PILL[t.priority],
                  )}
                >
                  {t.priority}
                </span>
              </div>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-control border border-rd-border py-2 text-sm font-medium text-rd-cyan hover:bg-rd-panel/50"
        >
          <Plus className="h-4 w-4" aria-hidden />
          Add Task
        </button>
      </div>

      {/* Quick Actions */}
      <div className="glow-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-rd-heading">Quick Actions</h3>
        <div className="grid grid-cols-3 gap-2">
          {QUICK_ACTIONS.map((a) => {
            const Icon = QA_ICON[a.icon];
            return (
              <button
                key={a.label}
                type="button"
                className="flex flex-col items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 p-3 text-center transition-colors hover:border-rd-border-hover"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <span className="text-[11px] font-medium leading-tight text-rd-body">
                  {a.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
