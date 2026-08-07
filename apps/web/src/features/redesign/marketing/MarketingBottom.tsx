"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight, FileText, Linkedin, Presentation, Video } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Delta, SampleTag } from "@/features/redesign/components";
import { ROI_TREND, TOP_CONTENT, TRAFFIC } from "./data";

const TYPE_ICON: Record<string, LucideIcon> = {
  "Blog Post": FileText,
  "LinkedIn Post": Linkedin,
  Video: Video,
  Webinar: Presentation,
  "Case Study": FileText,
};

export function MarketingBottom() {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <TrafficCard />
      <ContentCard />
      <RoiCard />
    </div>
  );
}

function CardHead({
  title,
  options = ["This Month", "This Quarter"],
}: {
  title: string;
  options?: string[];
}) {
  const [period, setPeriod] = useState(options[0]);
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      <select
        value={period}
        onChange={(e) => setPeriod(e.target.value)}
        aria-label="Period"
        className="h-8 rounded-control border border-rd-border bg-rd-panel/50 px-2 text-xs text-rd-body focus:border-rd-border-hover focus:outline-none"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function TrafficCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Traffic Overview" />
      <p className="text-xs text-rd-muted">Users</p>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-semibold tabular-nums text-rd-heading">58,642</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5">
        <Delta value={21.6} />
        <span className="text-xs text-rd-muted">vs last month</span>
      </div>
      <div className="mt-3 h-[180px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={TRAFFIC} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id="traffic-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--rd-cyan))" stopOpacity={0.35} />
                <stop offset="100%" stopColor="hsl(var(--rd-cyan))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--rd-border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => (v === 0 ? "0" : `${v / 1000}K`)}
              domain={[0, 60000]}
              ticks={[0, 15000, 30000, 45000, 60000]}
              width={38}
            />
            <Area
              type="monotone"
              dataKey="users"
              stroke="hsl(var(--rd-cyan))"
              strokeWidth={2}
              fill="url(#traffic-fill)"
              isAnimationActive={false}
              dot={{ r: 3, fill: "hsl(var(--rd-cyan))", strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ContentCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Top Content (by Engagement)" />
      <ul className="flex-1 space-y-3">
        {TOP_CONTENT.map((c) => {
          const Icon = TYPE_ICON[c.type] ?? FileText;
          return (
            <li key={c.title} className="flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel text-rd-cyan">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-rd-heading">{c.title}</p>
                <p className="truncate text-xs text-rd-muted">{c.type}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-sm font-semibold tabular-nums text-rd-heading">{c.engagement}</p>
                <Delta value={c.delta} className="justify-end text-[11px]" />
              </div>
            </li>
          );
        })}
      </ul>
      <FooterLink label="View all content" />
    </div>
  );
}

function RoiCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Marketing ROI Over Time" options={["This Quarter", "This Year"]} />
      <div className="flex items-end gap-2">
        <span className="text-3xl font-semibold tabular-nums text-rd-heading">380%</span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5">
        <Delta value={35.2} />
        <span className="text-xs text-rd-muted">vs last quarter</span>
      </div>
      <div className="mt-3 h-[180px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={ROI_TREND} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="var(--rd-border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: "hsl(var(--rd-muted))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
              domain={[0, 500]}
              ticks={[0, 100, 200, 300, 400, 500]}
              width={40}
            />
            <Line
              type="monotone"
              dataKey="roi"
              stroke="hsl(var(--rd-violet))"
              strokeWidth={2}
              isAnimationActive={false}
              dot={{ r: 3, fill: "hsl(var(--rd-violet))", strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-rd-border pt-4">
        <span className="text-xs text-rd-muted">Attributed Revenue</span>
        <span className="text-sm font-semibold tabular-nums text-rd-green">$6.24M</span>
      </div>
    </div>
  );
}

function FooterLink({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-control border border-rd-border py-2.5 text-sm font-medium text-rd-cyan transition-colors hover:border-rd-border-hover"
    >
      {label}
      <ArrowRight className="h-4 w-4" aria-hidden />
    </button>
  );
}
