import { cn } from "@/lib/cn";
import { GlowCard } from "./GlowCard";
import { round } from "./format";

export type AgentStatus = "active" | "idle" | "offline";

const STATUS: Record<AgentStatus, { dot: string; label: string; text: string }> = {
  active: { dot: "bg-rd-green", label: "Active", text: "text-rd-green" },
  idle: { dot: "bg-rd-amber", label: "Idle", text: "text-rd-amber" },
  offline: { dot: "bg-rd-muted", label: "Offline", text: "text-rd-muted" },
};

export interface AgentCardProps {
  name: string;
  role: string;
  /** Utilisation / load percentage, 0–100. */
  percent: number;
  status: AgentStatus;
  sample?: boolean;
}

/** Agent identity + role + load bar + status. */
export function AgentCard({ name, role, percent, status, sample }: AgentCardProps) {
  const s = STATUS[status];
  const pct = Math.max(0, Math.min(100, percent));
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <GlowCard sample={sample} className="p-4">
      <div className="flex items-center gap-3">
        <span className="gradient-ring relative flex h-10 w-10 items-center justify-center rounded-full bg-rd-panel text-sm font-semibold text-rd-heading">
          {initials}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-rd-heading">{name}</p>
          <p className="truncate text-xs text-rd-body">{role}</p>
        </div>
        <span className={cn("flex items-center gap-1.5 text-xs font-medium", s.text)}>
          <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} aria-hidden />
          {s.label}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-rd-panel">
          <div className="h-full rounded-full bg-rd-grad" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs tabular-nums text-rd-body">{round(pct)}%</span>
      </div>
    </GlowCard>
  );
}
