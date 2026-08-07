"use client";

import { cn } from "@/lib/cn";

export interface FunnelRow {
  label: string;
  /** Formatted primary value shown in the aligned right column (e.g. "$2.31M"). */
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

// Table-style funnel — NO text sits inside the tapering shapes. Each stage is a
// row: a colored funnel segment (narrowing top→bottom) on the left, the stage
// name, then value + count in a fixed right-hand column that lines up across
// rows. Nothing overlaps or clips, and it stays readable at laptop width.
export function Funnel({ rows, pctHeader, className }: FunnelProps) {
  const n = rows.length;
  const step = n > 1 ? 46 / (n - 1) : 0;
  const widthAt = (i: number) => 100 - i * step; // 100% → ~54% top edges

  return (
    <div className={cn("space-y-3", className)}>
      {/* Column headers */}
      <div className="flex items-center gap-3 text-[11px] uppercase tracking-wide text-rd-muted">
        <span className="w-20 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1">Stage</span>
        <span className="w-24 shrink-0 text-right">Value</span>
        {pctHeader && <span className="w-12 shrink-0 text-right">{pctHeader}</span>}
      </div>

      {rows.map((r, i) => {
        const topW = widthAt(i);
        const botW = widthAt(i + 1);
        const inset = ((topW - botW) / topW / 2) * 100; // side slope, % of bar
        return (
          <div key={r.label} className="flex items-center gap-3">
            {/* Funnel segment (visual only, no text) */}
            <div className="flex w-20 shrink-0 justify-center">
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
            {/* Stage name */}
            <span className="min-w-0 flex-1 text-sm font-medium text-rd-heading">{r.label}</span>
            {/* Value + count, aligned */}
            <div className="w-24 shrink-0 text-right leading-tight">
              <p className="text-sm font-semibold tabular-nums text-rd-heading">{r.value}</p>
              {r.sub && <p className="text-[11px] tabular-nums text-rd-muted">{r.sub}</p>}
            </div>
            {/* Conversion */}
            {pctHeader && (
              <span className="w-12 shrink-0 text-right text-xs font-medium tabular-nums text-rd-body">
                {r.pct ?? "—"}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
