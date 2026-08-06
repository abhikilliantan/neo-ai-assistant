"use client";

import {
  Cake,
  Download,
  FileText,
  GitFork,
  Lightbulb,
  Plane,
  Plus,
  Star,
  Trophy,
  Upload,
  UserPlus,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { AvatarStack, SampleTag } from "@/features/redesign/components";
import { AI_RECS, QUICK_ACTIONS, SNAPSHOT, TOP_PERFORMERS } from "./data";

const SNAP_ICON: Record<string, LucideIcon> = {
  cake: Cake,
  award: Trophy,
  plane: Plane,
  userplus: UserPlus,
};
const QA_ICON: Record<string, LucideIcon> = {
  add: Plus,
  report: FileText,
  review: Star,
  org: GitFork,
  import: Upload,
  export: Download,
};
const REC_TONE: Record<string, string> = {
  cyan: "text-rd-cyan",
  amber: "text-rd-amber",
  green: "text-rd-green",
};

export function PeopleRightRail() {
  return (
    <div className="space-y-4">
      {/* Today's People Snapshot */}
      <div className="glow-card p-4">
        <Head title="Today's People Snapshot" />
        <ul className="space-y-3">
          {SNAPSHOT.map((s) => {
            const Icon = SNAP_ICON[s.icon];
            return (
              <li key={s.label} className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-rd-heading">{s.label}</p>
                  <p className="text-lg font-semibold tabular-nums text-rd-heading">{s.count}</p>
                </div>
                <AvatarStack names={s.people} size={24} />
              </li>
            );
          })}
        </ul>
      </div>

      {/* Top Performers */}
      <div className="glow-card p-4">
        <Head title="Top Performers" />
        <ul className="space-y-3">
          {TOP_PERFORMERS.map((p, i) => (
            <li key={p.name} className="flex items-center gap-3">
              <span className="w-4 shrink-0 text-sm font-semibold text-rd-muted">{i + 1}</span>
              <AvatarStack names={[p.name]} size={32} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{p.name}</p>
                <p className="truncate text-xs text-rd-muted">{p.dept}</p>
              </div>
              <MiniRing pct={p.pct} />
            </li>
          ))}
        </ul>
      </div>

      {/* Quick Actions */}
      <div className="glow-card p-4">
        <h3 className="mb-3 text-sm font-semibold text-rd-heading">Quick Actions</h3>
        <div className="grid grid-cols-2 gap-2">
          {QUICK_ACTIONS.map((a) => {
            const Icon = QA_ICON[a.icon];
            return (
              <button
                key={a.label}
                type="button"
                className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-panel/50 px-3 py-2.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
              >
                <Icon className="h-4 w-4 shrink-0 text-rd-cyan" aria-hidden />
                <span className="truncate">{a.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* AI Recommendations */}
      <div className="glow-card p-4">
        <Head title="AI Recommendations" />
        <ul className="space-y-3">
          {AI_RECS.map((r) => (
            <li key={r.text} className="flex items-start gap-2.5">
              <Lightbulb className={cn("mt-0.5 h-4 w-4 shrink-0", REC_TONE[r.tone])} aria-hidden />
              <p className="text-sm text-rd-body">{r.text}</p>
            </li>
          ))}
        </ul>
        <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-rd-cyan">
          View all recommendations →
        </span>
      </div>
    </div>
  );
}

function Head({ title }: { title: string }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      <span className="text-xs font-medium text-rd-cyan">View all</span>
    </div>
  );
}

function MiniRing({ pct }: { pct: number }) {
  const color = pct >= 88 ? "hsl(var(--rd-green))" : "hsl(var(--rd-amber))";
  return (
    <div
      className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${color} ${pct}%, hsl(var(--rd-panel)) 0)` }}
    >
      <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-rd-card text-[10px] font-semibold tabular-nums text-rd-heading">
        {pct}
      </span>
    </div>
  );
}
