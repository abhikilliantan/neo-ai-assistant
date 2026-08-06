"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { AvatarStack, SampleTag } from "@/features/redesign/components";
import { CAL_SLOTS, DAY_LABEL, type CalSlot, type SlotColor } from "./data";

const BORDER: Record<SlotColor, string> = {
  rose: "border-l-rd-rose",
  cyan: "border-l-rd-cyan",
  violet: "border-l-rd-violet",
  green: "border-l-rd-green",
  amber: "border-l-rd-amber",
};
const TINT: Record<SlotColor, string> = {
  rose: "bg-rd-rose/5",
  cyan: "bg-rd-cyan/5",
  violet: "bg-rd-violet/10",
  green: "bg-rd-green/5",
  amber: "bg-rd-amber/5",
};

export function DayCalendar() {
  return (
    <div className="glow-card flex min-w-0 flex-col p-0">
      <div className="flex items-center justify-between border-b border-rd-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-rd-heading">{DAY_LABEL}</h2>
          <SampleTag />
        </div>
        <div className="flex items-center gap-1">
          <NavBtn label="Previous day" icon={ChevronLeft} />
          <button
            type="button"
            className="rounded-control border border-rd-border px-2.5 py-1 text-xs font-medium text-rd-body hover:text-rd-heading"
          >
            Today
          </button>
          <NavBtn label="Next day" icon={ChevronRight} />
        </div>
      </div>

      <div className="flex-1 space-y-1 px-3 py-3">
        {CAL_SLOTS.map((s) => (
          <Slot key={s.title} slot={s} />
        ))}
      </div>

      <button
        type="button"
        className="border-t border-rd-border py-3 text-center text-sm font-medium text-rd-cyan hover:bg-rd-panel/50"
      >
        View full calendar
      </button>
    </div>
  );
}

function Slot({ slot }: { slot: CalSlot }) {
  return (
    <div>
      <div className="flex gap-3">
        <span className="w-16 shrink-0 pt-2 text-right text-[11px] tabular-nums text-rd-muted">
          {slot.time}
        </span>
        <div
          className={cn(
            "min-w-0 flex-1 rounded-r-lg border-l-2 px-3 py-2",
            BORDER[slot.color],
            TINT[slot.color],
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate text-sm font-medium text-rd-heading">{slot.title}</p>
            {slot.priority && (
              <span className="shrink-0 rounded-full border border-rd-rose/40 bg-rd-rose/10 px-2 py-0.5 text-[10px] font-medium text-rd-rose">
                {slot.priority}
              </span>
            )}
          </div>
          {slot.range && (
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className="text-xs text-rd-muted">{slot.range}</span>
              {slot.attendees && (
                <AvatarStack names={slot.attendees} extra={slot.extra} size={22} />
              )}
            </div>
          )}
        </div>
      </div>
      {slot.now && (
        <div className="my-1 flex items-center gap-2 pl-16">
          <span className="rounded bg-rd-cyan px-1.5 py-0.5 text-[10px] font-semibold text-white">
            11:24 AM
          </span>
          <span className="h-px flex-1 bg-rd-cyan" aria-hidden />
        </div>
      )}
    </div>
  );
}

function NavBtn({ label, icon: Icon }: { label: string; icon: typeof ChevronLeft }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="flex h-7 w-7 items-center justify-center rounded-control border border-rd-border text-rd-muted hover:text-rd-heading"
    >
      <Icon className="h-4 w-4" aria-hidden />
    </button>
  );
}
