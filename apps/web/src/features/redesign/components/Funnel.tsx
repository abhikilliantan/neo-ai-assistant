"use client";

import { cn } from "@/lib/cn";

export interface FunnelRow {
  label: string;
  /** Formatted primary value shown on the right inside the bar (e.g. "$2.31M"). */
  value: string;
  /** Optional secondary note next to the value (e.g. count "265"). */
  sub?: string;
  /** Conversion / rate label shown in the side column (e.g. "68%"). */
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

// Trapezoid funnel: each stage narrows toward the next, its bottom edge matching
// the following stage's width so the segments read as one continuous funnel.
export function Funnel({ rows, pctHeader, className }: FunnelProps) {
  const n = rows.length;
  const step = n > 1 ? 46 / (n - 1) : 0;
  const widthAt = (i: number) => 100 - i * step; // 100% → ~54% top edges

  return (
    <div className={cn("flex gap-3", className)}>
      <div className="min-w-0 flex-1 space-y-1.5">
        {rows.map((r, i) => {
          const topW = widthAt(i);
          const botW = widthAt(i + 1);
          const inset = ((topW - botW) / topW / 2) * 100; // side slope, % of bar
          return (
            <div key={r.label} className="flex justify-center">
              <div
                className="flex items-center justify-between gap-2 px-4 py-2.5 text-white"
                style={{
                  width: `${topW}%`,
                  background: r.color,
                  clipPath: `polygon(0 0, 100% 0, ${100 - inset}% 100%, ${inset}% 100%)`,
                }}
              >
                <span className="truncate text-sm font-medium">{r.label}</span>
                <span className="shrink-0 text-sm font-semibold tabular-nums">
                  {r.value}
                  {r.sub && <span className="ml-1 font-normal opacity-80">({r.sub})</span>}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {pctHeader && (
        <div className="flex w-16 shrink-0 flex-col">
          <span className="mb-1.5 text-right text-[11px] uppercase tracking-wide text-rd-muted">
            {pctHeader}
          </span>
          <div className="flex flex-1 flex-col justify-around">
            {rows.map((r) => (
              <span
                key={r.label}
                className="flex h-9 items-center justify-center rounded-full border border-rd-border bg-rd-panel/60 text-xs font-medium tabular-nums text-rd-body"
              >
                {r.pct ?? "—"}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
