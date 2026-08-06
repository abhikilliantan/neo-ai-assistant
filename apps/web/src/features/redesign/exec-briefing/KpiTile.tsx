import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { Delta, SampleTag } from "@/features/redesign/components";

export type Tone = "cyan" | "green" | "violet" | "amber";

const ICON_TONE: Record<Tone, string> = {
  cyan: "border-rd-cyan/30 bg-rd-cyan/10 text-rd-cyan",
  green: "border-rd-green/30 bg-rd-green/10 text-rd-green",
  violet: "border-rd-violet/30 bg-rd-violet/10 text-rd-violet",
  amber: "border-rd-amber/30 bg-rd-amber/10 text-rd-amber",
};

export interface KpiTileProps {
  icon: LucideIcon;
  tone?: Tone;
  label: string;
  value: string;
  /** Percentage delta (uses the Delta pill). */
  delta?: number;
  /** Freeform delta text, e.g. "+12 new" (green). Overrides `delta`. */
  deltaText?: string;
  note?: string;
  sample?: boolean;
  /** Chart area (Sparkline / RingGauge / MiniBars). */
  children?: React.ReactNode;
}

export function KpiTile({
  icon: Icon,
  tone = "cyan",
  label,
  value,
  delta,
  deltaText,
  note,
  sample,
  children,
}: KpiTileProps) {
  return (
    <div className="glow-card p-4">
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-control border",
            ICON_TONE[tone],
          )}
        >
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        {sample && <SampleTag />}
      </div>
      <p className="mt-3 text-[11px] font-medium uppercase tracking-wide text-rd-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-semibold tabular-nums text-rd-heading">{value}</p>
      <div className="mt-1 flex items-center gap-2">
        {deltaText ? (
          <span className="text-xs font-medium text-rd-green">{deltaText}</span>
        ) : (
          delta !== undefined && <Delta value={delta} />
        )}
        {note && <span className="text-xs text-rd-muted">{note}</span>}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
