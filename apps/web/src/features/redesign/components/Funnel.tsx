"use client";

import { cn } from "@/lib/cn";

export interface FunnelRow {
  label: string;
  /** Formatted primary value shown inside the trapezoid (e.g. "$2.31M"). */
  value: string;
  /** Optional secondary note under the stage label (e.g. count "265"). */
  sub?: string;
  /** Conversion / rate label shown in the side pill (e.g. "68%"). */
  pct?: string;
  /** CSS fill color (e.g. "hsl(var(--rd-cyan))"). */
  color: string;
}

export interface FunnelProps {
  rows: FunnelRow[];
  /** Header for the side conversion column. Omit to hide the column. */
  pctHeader?: string;
  className?: string;
}

// Trapezoid funnel. The stage name + count sit to the LEFT of each segment so
// long labels never clip; the value sits centered INSIDE the trapezoid; the
// optional conversion rate is a pill on the right. Each stage narrows toward the
// next, its bottom edge matching the following stage's width so the segments
// read as one continuous funnel.
export function Funnel({ rows, pctHeader, className }: FunnelProps) {
  const n = rows.length;
  const step = n > 1 ? 46 / (n - 1) : 0;
  const widthAt = (i: number) => 100 - i * step; // 100% → ~54% top edges

  return (
    <div className={cn("space-y-2", className)}>
      {pctHeader && (
        <div className="flex items-center gap-3">
          <span className="w-24 shrink-0" aria-hidden />
          <span className="flex-1" aria-hidden />
          <span className="w-14 shrink-0 text-right text-[11px] uppercase tracking-wide text-rd-muted">
            {pctHeader}
          </span>
        </div>
      )}
      {rows.map((r, i) => {
        const topW = widthAt(i);
        const botW = widthAt(i + 1);
        const inset = ((topW - botW) / topW / 2) * 100; // side slope, % of bar
        return (
          <div key={r.label} className="flex items-center gap-3">
            <div className="w-24 shrink-0 text-right leading-tight">
              <p className="text-xs font-medium text-rd-heading">{r.label}</p>
              {r.sub && <p className="text-[11px] tabular-nums text-rd-muted">{r.sub}</p>}
            </div>
            <div className="flex min-w-0 flex-1 justify-center">
              <div
                className="flex items-center justify-center px-2 py-2 text-white"
                style={{
                  width: `${topW}%`,
                  background: r.color,
                  clipPath: `polygon(0 0, 100% 0, ${100 - inset}% 100%, ${inset}% 100%)`,
                }}
              >
                <span className="text-xs font-semibold tabular-nums">{r.value}</span>
              </div>
            </div>
            {pctHeader && (
              <span className="flex w-14 shrink-0 items-center justify-center rounded-full border border-rd-border bg-rd-panel/60 px-2 py-1 text-xs font-medium tabular-nums text-rd-body">
                {r.pct ?? "—"}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
