import { Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { GlowCard } from "./GlowCard";
import { SampleTag } from "./SampleTag";
import { round } from "./format";

export type ProjectStatus = "on-track" | "at-risk" | "delayed";
export type RiskLevel = "low" | "medium" | "high";

const STATUS_TAG: Record<ProjectStatus, { label: string; cls: string }> = {
  "on-track": { label: "On track", cls: "border-rd-green/40 bg-rd-green/10 text-rd-green" },
  "at-risk": { label: "At risk", cls: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber" },
  delayed: { label: "Delayed", cls: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose" },
};

const RISK_TEXT: Record<RiskLevel, string> = {
  low: "text-rd-green",
  medium: "text-rd-amber",
  high: "text-rd-rose",
};

export interface ProjectCardProps {
  name: string;
  status: ProjectStatus;
  /** Completion percentage, 0–100. */
  progress: number;
  owner: string;
  risk: RiskLevel;
  /** Short AI-generated prediction / forecast line. */
  prediction: string;
  sample?: boolean;
}

/** Project row: name + status tag + progress + owner + risk + AI prediction. */
export function ProjectCard({
  name,
  status,
  progress,
  owner,
  risk,
  prediction,
  sample,
}: ProjectCardProps) {
  const tag = STATUS_TAG[status];
  const pct = Math.max(0, Math.min(100, progress));

  return (
    <GlowCard>
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-2 font-semibold text-rd-heading">{name}</p>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            tag.cls,
          )}
        >
          {tag.label}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-rd-panel">
          <div className="h-full rounded-full bg-rd-grad" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs tabular-nums text-rd-body">{round(pct)}%</span>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 text-xs">
        <span className="truncate text-rd-body">
          Owner <span className="text-rd-heading">{owner}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {sample && <SampleTag />}
          <span className={cn("font-medium capitalize", RISK_TEXT[risk])}>{risk} risk</span>
        </span>
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-control border border-rd-border bg-rd-panel/60 p-2.5">
        <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rd-violet" aria-hidden />
        <p className="text-xs leading-relaxed text-rd-body">{prediction}</p>
      </div>
    </GlowCard>
  );
}
