"use client";

import Link from "next/link";
import type { Route } from "next";
import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  FileText,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SampleTag } from "@/features/redesign/components";

// Static "Related Information" targets. Only Project Dashboard has a real /neo
// route today; the rest are illustrative (the whole section carries a
// SampleTag when Demo mode is off, so they read as placeholder).
const RELATED: Array<{ icon: LucideIcon; title: string; action: string; href?: string }> = [
  { icon: CalendarClock, title: "Project Timeline", action: "View timeline" },
  { icon: BarChart3, title: "Project Dashboard", action: "Open dashboard", href: "/neo/dashboard" },
  { icon: FileText, title: "Risk Register", action: "View risks" },
  { icon: Users, title: "Team Activity", action: "24 members active" },
];

const NEXT_ACTIONS = [
  "Review project timeline",
  "Check resource allocation",
  "View budget vs actual",
  "Schedule project review meeting",
];

export function ContextRail({
  lastQuestion,
  className,
}: {
  lastQuestion: string | null;
  className?: string;
}) {
  return (
    <aside className={className}>
      <div className="space-y-4">
        {/* Context Awareness — live, derived from the real current question. */}
        <div className="glow-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-rd-heading">Context Awareness</h3>
            <span className="inline-flex items-center gap-1 text-xs font-medium text-rd-green">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rd-green" aria-hidden />
              Live
            </span>
          </div>
          <div className="rounded-control border border-rd-border bg-rd-panel/50 p-3">
            <p className="text-xs text-rd-muted">You are asking about</p>
            <p className="mt-1 line-clamp-2 text-sm font-medium text-rd-heading">
              {lastQuestion ?? "Ask a question to begin"}
            </p>
            {lastQuestion && (
              <p className="mt-2 text-xs text-rd-muted">Tracked from your current thread</p>
            )}
          </div>
        </div>

        {/* Related Information */}
        <div className="glow-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Related Information</h3>
            <SampleTag />
          </div>
          <ul className="space-y-1">
            {RELATED.map((r) => {
              const inner = (
                <>
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel">
                      <r.icon className="h-4 w-4 text-rd-cyan" aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-rd-heading">
                        {r.title}
                      </span>
                      <span className="block truncate text-xs text-rd-cyan">{r.action}</span>
                    </span>
                  </span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-rd-muted" aria-hidden />
                </>
              );
              const rowCls =
                "flex items-center justify-between gap-2 rounded-control px-2 py-2 transition-colors hover:bg-rd-panel";
              return (
                <li key={r.title}>
                  {r.href ? (
                    <Link href={r.href as Route} className={rowCls}>
                      {inner}
                    </Link>
                  ) : (
                    <div className={rowCls}>{inner}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* AI Insights */}
        <div className="glow-card p-4">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">AI Insights</h3>
            <SampleTag />
          </div>
          <p className="mb-3 text-xs text-rd-muted">Based on your data</p>
          <div className="rounded-control border border-rd-border bg-rd-panel/50 p-3">
            <div className="flex items-start gap-2">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-rd-violet" aria-hidden />
              <div className="min-w-0">
                <p className="text-sm font-medium text-rd-heading">
                  Project is on track for target date
                </p>
                <p className="mt-0.5 text-xs text-rd-muted">AI confidence: 92%</p>
              </div>
            </div>
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-rd-panel">
              <div className="h-full rounded-full bg-rd-grad" style={{ width: "92%" }} />
            </div>
            <p className="mt-3 text-xs text-rd-body">
              Similar projects with this pattern have an 89% success rate.
            </p>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-rd-cyan">
              View analysis <ArrowRight className="h-3 w-3" aria-hidden />
            </span>
          </div>
        </div>

        {/* Suggested Next Actions */}
        <div className="glow-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="text-sm font-semibold text-rd-heading">Suggested Next Actions</h3>
            <SampleTag />
          </div>
          <ul className="space-y-1">
            {NEXT_ACTIONS.map((a) => (
              <li
                key={a}
                className="flex items-center justify-between gap-2 rounded-control px-2 py-2 text-sm text-rd-body"
              >
                <span className="inline-flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-rd-cyan" aria-hidden />
                  {a}
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-rd-muted" aria-hidden />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
}
