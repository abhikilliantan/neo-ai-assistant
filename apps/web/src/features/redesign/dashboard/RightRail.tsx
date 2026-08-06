"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  BarChart3,
  CalendarPlus,
  FileText,
  MessageSquare,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { AlertRow, GlowCard, QuickActionButton, SampleTag } from "@/features/redesign/components";
import { navHref } from "@/features/redesign/shell";
import { SAMPLE_ALERTS, SAMPLE_INSIGHTS, SAMPLE_MEETINGS, SAMPLE_RECS } from "./data";

const QUICK_ACTIONS: { icon: typeof MessageSquare; label: string; href: Route }[] = [
  { icon: MessageSquare, label: "Launch AI Chat", href: navHref("ai-chat") },
  { icon: FileText, label: "Generate Report", href: navHref("reports") },
  { icon: ShieldAlert, label: "Approve Purchase", href: navHref("finance") },
  { icon: BarChart3, label: "View Risks", href: navHref("analytics") },
  { icon: CalendarPlus, label: "Create Meeting", href: navHref("meetings") },
];

export function RightRail() {
  const router = useRouter();

  return (
    <div className="space-y-4">
      {/* Upcoming Meetings */}
      <RailCard title="Upcoming Meetings" sample>
        <ul className="space-y-2.5">
          {SAMPLE_MEETINGS.map((m) => (
            <li key={m.title} className="flex items-start gap-3">
              <span className="w-12 shrink-0 text-xs font-medium tabular-nums text-rd-cyan">
                {m.time}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-rd-heading">{m.title}</span>
                <span className="block truncate text-xs text-rd-muted">{m.who}</span>
              </span>
            </li>
          ))}
        </ul>
      </RailCard>

      {/* Critical Alerts */}
      <RailCard title="Critical Alerts" sample>
        <div>
          {SAMPLE_ALERTS.map((a) => (
            <AlertRow key={a.title} severity={a.severity} title={a.title} meta={a.meta} />
          ))}
        </div>
      </RailCard>

      {/* AI Recommendations */}
      <RailCard title="AI Recommendations" sample>
        <ul className="space-y-2.5">
          {SAMPLE_RECS.map((r) => (
            <li key={r} className="flex items-start gap-2 text-sm text-rd-body">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rd-violet" aria-hidden />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </RailCard>

      {/* Quick Actions — real navigation */}
      <RailCard title="Quick Actions">
        <div className="grid grid-cols-2 gap-2.5">
          {QUICK_ACTIONS.map((a) => (
            <QuickActionButton
              key={a.label}
              icon={a.icon}
              label={a.label}
              onClick={() => router.push(a.href)}
            />
          ))}
        </div>
      </RailCard>

      {/* Executive Insights */}
      <RailCard title="Executive Insights" sample>
        <ul className="space-y-2.5">
          {SAMPLE_INSIGHTS.map((s) => (
            <li key={s} className="flex items-start gap-2 text-sm text-rd-body">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rd-grad" aria-hidden />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </RailCard>
    </div>
  );
}

function RailCard({
  title,
  sample,
  children,
}: {
  title: string;
  sample?: boolean;
  children: React.ReactNode;
}) {
  return (
    <GlowCard className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        {sample && <SampleTag />}
      </div>
      {children}
    </GlowCard>
  );
}
