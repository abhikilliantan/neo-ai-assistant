"use client";

import { cn } from "@/lib/cn";

export interface FunnelRow {
  label: string;
  /** Formatted primary value shown in the aligned value column (e.g. "$2.31M"). */
  value: string;
  /** Optional secondary note under the value (e.g. count "265"). */
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

// Strict 4-column CSS grid. Each column is its own grid track with a gap, so
// text physically cannot overlap a neighbor — no absolute positioning, no text
// drawn over the funnel shape.
//   [ funnel segment ] [ stage name ] [ value + count ] [ conv % ]
export function Funnel({ rows, pctHeader, className }: FunnelProps) {
  const n = rows.length;
  const step = n > 1 ? 46 / (n - 1) : 0;
  const widthAt = (i: number) => 100 - i * step; // 100% → ~54% top edges

  // Grid tracks: segment | stage (flex, gets the remainder) | value | conv.
  // Fixed tracks are kept small so the stage-name column never collapses to 0
  // even in a narrow (~230px) card. Drop the conv track when it's hidden.
  const cols = pctHeader
    ? "grid-cols-[2rem_minmax(0,1fr)_3.5rem_2rem]"
    : "grid-cols-[2rem_minmax(0,1fr)_3.5rem]";

  return (
    <div className={cn("space-y-3", className)}>
      {/* Column headers — same grid template as the rows */}
      <div
        className={cn(
          "grid items-center gap-2 text-[11px] uppercase tracking-wide text-rd-muted",
          cols,
        )}
      >
        <span aria-hidden />
        <span className="min-w-0">Stage</span>
        <span className="text-right">Value</span>
        {pctHeader && <span className="text-right">{pctHeader}</span>}
      </div>

      {rows.map((r, i) => {
        const topW = widthAt(i);
        const botW = widthAt(i + 1);
        const inset = ((topW - botW) / topW / 2) * 100; // side slope, % of bar
        return (
          <div key={r.label} className={cn("grid items-center gap-2", cols)}>
            {/* Col 1 — funnel segment (visual only, no text) */}
            <div className="flex justify-center">
              <div
                className="h-8"
                style={{
                  width: `${topW}%`,
                  background: r.color,
                  clipPath: `polygon(0 0, 100% 0, ${100 - inset}% 100%, ${inset}% 100%)`,
                }}
                aria-hidden
              />
            </div>
            {/* Col 2 — stage name */}
            <span className="min-w-0 truncate text-sm font-medium text-rd-heading">{r.label}</span>
            {/* Col 3 — value + count, stacked */}
            <div className="text-right leading-tight">
              <p className="text-sm font-semibold tabular-nums text-rd-heading">{r.value}</p>
              {r.sub && <p className="text-[11px] tabular-nums text-rd-muted">{r.sub}</p>}
            </div>
            {/* Col 4 — conversion */}
            {pctHeader && (
              <span className="text-right text-xs font-medium tabular-nums text-rd-body">
                {r.pct ?? "—"}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
