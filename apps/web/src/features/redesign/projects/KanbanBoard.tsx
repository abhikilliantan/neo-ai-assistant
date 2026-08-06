"use client";

import { Check, ChevronRight, Plus } from "lucide-react";
import { cn } from "@/lib/cn";
import { RingGauge, SampleTag } from "@/features/redesign/components";
import { STATUS_PILL, type KanbanCard, type KanbanColumn } from "./data";

export function KanbanBoard({ columns }: { columns: KanbanColumn[] }) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="grid min-w-[1100px] grid-cols-5 gap-4">
        {columns.map((col) => (
          <Column key={col.key} col={col} />
        ))}
      </div>
    </div>
  );
}

function Column({ col }: { col: KanbanColumn }) {
  return (
    <div className="flex min-w-0 flex-col rounded-card border border-rd-border bg-rd-panel/40">
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className={cn("text-sm font-semibold", col.accent)}>{col.title}</span>
        <span className="flex items-center gap-1.5">
          <span className="rounded-full border border-rd-border bg-rd-card px-1.5 py-0.5 text-[11px] font-medium text-rd-body">
            {col.count}
          </span>
          <ChevronRight className="h-3.5 w-3.5 text-rd-muted" aria-hidden />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2.5 px-2.5 pb-2.5">
        {col.cards.map((c) => (
          <Card key={c.name} card={c} />
        ))}
      </div>
      <button
        type="button"
        className="flex items-center justify-center gap-1.5 border-t border-rd-border py-2.5 text-xs font-medium text-rd-muted transition-colors hover:text-rd-heading"
      >
        <Plus className="h-3.5 w-3.5" aria-hidden />
        Add Project
      </button>
    </div>
  );
}

function Card({ card }: { card: KanbanCard }) {
  const done = card.status === "Completed";
  return (
    <div className="glow-card p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-rd-heading">{card.name}</p>
          <p className="truncate text-xs text-rd-muted">{card.company}</p>
        </div>
        {done ? (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-rd-green/40 bg-rd-green/10 text-rd-green">
            <Check className="h-4 w-4" aria-hidden />
          </span>
        ) : (
          <RingGauge value={card.progress} size={44} />
        )}
      </div>

      <div className="mt-3 flex items-end justify-between gap-2">
        <div className="min-w-0 text-xs text-rd-muted">
          {card.plannedStart && (
            <>
              <p>Planned Start</p>
              <p className="text-rd-body">{card.plannedStart}</p>
            </>
          )}
          {card.due && (
            <>
              <p>Due: {card.due}</p>
              {card.owner && <p>Owner: {card.owner}</p>}
            </>
          )}
          {card.completedOn && (
            <>
              <p>Completed on</p>
              <p className="text-rd-body">{card.completedOn}</p>
            </>
          )}
        </div>
        <span className="flex shrink-0 items-center gap-1">
          {!card.real && !card.plannedStart && <SampleTag />}
          {done ? (
            <span className="text-xs font-semibold text-rd-green">100%</span>
          ) : (
            card.status && (
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[10px] font-medium",
                  STATUS_PILL[card.status],
                )}
              >
                {card.status}
              </span>
            )
          )}
        </span>
      </div>
    </div>
  );
}
