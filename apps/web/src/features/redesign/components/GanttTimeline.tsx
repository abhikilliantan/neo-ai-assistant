import { cn } from "@/lib/cn";

export type GanttStatus = "on-track" | "at-risk" | "delayed" | "completed";

export interface GanttRow {
  name: string;
  /** Bar start, in month units from the first column (0-based, fractions ok). */
  start: number;
  /** Bar length in month units. */
  span: number;
  status: GanttStatus;
  /** Short label rendered at the bar's end (e.g. a due date). */
  endLabel?: string;
}

export interface GanttTimelineProps {
  months: string[];
  rows: GanttRow[];
  /** Width of the left project-name column. */
  labelWidth?: number;
  className?: string;
}

const BAR: Record<GanttStatus, string> = {
  "on-track": "bg-rd-green",
  "at-risk": "bg-rd-amber",
  delayed: "bg-rd-rose",
  completed: "bg-rd-cyan",
};

/** Lightweight gantt: a project per row with a positioned status bar across a
 *  month grid. Pure CSS (no chart lib) — positions are % of the month track. */
export function GanttTimeline({ months, rows, labelWidth = 180, className }: GanttTimelineProps) {
  const total = months.length;
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <div className="min-w-[520px]">
        {/* Month header */}
        <div className="flex items-center" style={{ paddingLeft: labelWidth }}>
          {months.map((m) => (
            <div key={m} className="flex-1 text-xs text-rd-muted">
              {m}
            </div>
          ))}
        </div>

        {/* Rows */}
        <div className="mt-2 space-y-3">
          {rows.map((r) => (
            <div key={r.name} className="flex items-center">
              <div
                className="shrink-0 truncate pr-3 text-sm text-rd-body"
                style={{ width: labelWidth }}
              >
                {r.name}
              </div>
              <div className="relative h-6 flex-1">
                {/* gridlines */}
                <div className="absolute inset-0 flex">
                  {months.map((m) => (
                    <div key={m} className="flex-1 border-l border-rd-border/50 first:border-l-0" />
                  ))}
                </div>
                {/* bar */}
                <div
                  className={cn(
                    "absolute top-1/2 flex h-2.5 -translate-y-1/2 items-center rounded-full",
                    BAR[r.status],
                  )}
                  style={{
                    left: `${(r.start / total) * 100}%`,
                    width: `${(r.span / total) * 100}%`,
                  }}
                />
                {r.endLabel && (
                  <span
                    className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-1.5 text-[11px] text-rd-muted"
                    style={{ left: `${((r.start + r.span) / total) * 100}%` }}
                  >
                    {r.endLabel}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
