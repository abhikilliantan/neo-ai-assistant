"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Delta, Donut, Funnel, RingGauge, SampleTag } from "@/features/redesign/components";
import { HEADCOUNT, HEADCOUNT_TOTAL, HEAD_TREND, RECRUITMENT } from "./data";

export function HrBand() {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <RecruitmentCard />
      <HeadcountCard />
      <div className="flex flex-col gap-5">
        <EngagementCard />
        <TrendCard />
      </div>
    </div>
  );
}

function CardHead({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      {right}
    </div>
  );
}

function RecruitmentCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Recruitment Pipeline" />
      <p className="mb-3 text-center text-xs text-rd-muted">
        Total Applicants <span className="text-base font-semibold text-rd-heading">1,240</span>
      </p>
      <Funnel rows={RECRUITMENT} pctHeader="Conv." className="flex-1" />
      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-rd-border pt-4">
        <Stat label="Offer Acceptance" value="84%" tone="text-rd-green" />
        <Stat label="Avg. Time to Hire" value="24 Days" tone="text-rd-heading" />
      </div>
    </div>
  );
}

function HeadcountCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Headcount by Department" />
      <div className="flex items-center gap-4">
        <Donut
          data={HEADCOUNT.map((s) => ({ label: s.label, value: s.value, color: s.color }))}
          centerValue={HEADCOUNT_TOTAL}
          centerLabel="Total"
          size={150}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-2">
          {HEADCOUNT.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="shrink-0 tabular-nums text-rd-muted">{s.pct}</span>
              <span className="w-8 shrink-0 text-right tabular-nums text-rd-heading">
                {s.value}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function EngagementCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Employee Engagement" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col items-center">
          <RingGauge value={84} size={104} />
          <span className="mt-1 text-xs text-rd-muted">eNPS +42</span>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <Stat label="Survey Participation" value="92%" tone="text-rd-heading" />
          <Stat label="Manager Effectiveness" value="4.3 / 5" tone="text-rd-heading" />
          <div>
            <p className="text-[11px] text-rd-muted">QoQ Change</p>
            <Delta value={4} suffix="pt" className="mt-0.5 text-sm" />
          </div>
        </div>
      </div>
    </div>
  );
}

function TrendCard() {
  return (
    <div className="glow-card p-5">
      <CardHead title="Headcount Trend" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col">
          <span className="text-2xl font-semibold tabular-nums text-rd-heading">256</span>
          <Delta value={12} suffix="" className="text-sm" />
          <span className="mt-0.5 text-xs text-rd-muted">this month</span>
        </div>
        <div className="h-[96px] min-w-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={HEAD_TREND} margin={{ top: 4, right: 4, bottom: 0, left: -28 }}>
              <CartesianGrid stroke="var(--rd-border)" vertical={false} />
              <XAxis dataKey="label" hide />
              <YAxis hide domain={[200, 260]} />
              <Line
                type="monotone"
                dataKey="headcount"
                stroke="hsl(var(--rd-cyan))"
                strokeWidth={2}
                isAnimationActive={false}
                dot={{ r: 2.5, fill: "hsl(var(--rd-cyan))", strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div>
      <p className="text-[11px] text-rd-muted">{label}</p>
      <p className={`mt-0.5 text-sm font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}
