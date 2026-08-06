import type { LucideIcon } from "lucide-react";
import { GlowCard } from "./GlowCard";
import { Delta } from "./Delta";
import { SampleTag } from "./SampleTag";
import { round } from "./format";

export interface StatTileProps {
  icon: LucideIcon;
  label: string;
  value: number | string;
  /** Signed percentage change; omit to hide the delta. */
  delta?: number;
  /** Marks the value as placeholder — renders an inline SampleTag by the label. */
  sample?: boolean;
}

/** Compact icon + label + value + delta tile. */
export function StatTile({ icon: Icon, label, value, delta, sample }: StatTileProps) {
  return (
    <GlowCard className="p-4">
      <div className="flex items-start justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-control border border-rd-border bg-rd-panel text-rd-cyan">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        {delta !== undefined && <Delta value={delta} />}
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums text-rd-heading">
        {typeof value === "number" ? round(value) : value}
      </p>
      <div className="mt-0.5 flex items-center gap-1.5">
        <p className="text-sm text-rd-body">{label}</p>
        {sample && <SampleTag />}
      </div>
    </GlowCard>
  );
}
