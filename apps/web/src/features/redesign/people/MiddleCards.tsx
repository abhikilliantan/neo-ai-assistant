"use client";

import { User, UserRound } from "lucide-react";
import { Delta, Donut, SampleTag } from "@/features/redesign/components";
import { DIVERSITY, ENGAGEMENT, HEADCOUNT } from "./data";

export function MiddleCards() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <HeadcountCard />
      <EngagementCard />
      <DiversityCard />
    </div>
  );
}

function CardHeader({ title, action }: { title: string; action: string }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      <span className="text-xs font-medium text-rd-cyan">{action}</span>
    </div>
  );
}

function HeadcountCard() {
  return (
    <div className="glow-card p-5">
      <CardHeader title="Headcount by Department" action="View details" />
      <div className="flex items-center gap-4">
        <Donut
          data={HEADCOUNT.slices.map((s) => ({ label: s.label, value: s.value, color: s.color }))}
          centerValue={HEADCOUNT.total}
          centerLabel="Total"
          size={150}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-1.5">
          {HEADCOUNT.slices.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="shrink-0 tabular-nums text-rd-heading">{s.value}</span>
              <span className="shrink-0 text-rd-muted">({s.pct})</span>
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
      <CardHeader title="Employee Engagement Score" action="View insights" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col items-center">
          <div
            className="relative flex h-24 w-24 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(hsl(var(--rd-violet)) ${ENGAGEMENT.score}%, hsl(var(--rd-panel)) 0)`,
            }}
          >
            <div className="flex h-[76px] w-[76px] flex-col items-center justify-center rounded-full bg-rd-card">
              <span className="text-xl font-semibold tabular-nums text-rd-heading">
                {ENGAGEMENT.score}%
              </span>
              <span className="text-[11px] text-rd-muted">Engaged</span>
            </div>
          </div>
          <span className="mt-2 inline-flex items-center gap-1 text-xs">
            <Delta value={ENGAGEMENT.delta} />
            <span className="text-rd-muted">vs last month</span>
          </span>
        </div>
        <ul className="min-w-0 flex-1 space-y-2.5">
          {ENGAGEMENT.bars.map((b) => (
            <li key={b.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="min-w-0 truncate text-rd-body">{b.label}</span>
                <span className="shrink-0 tabular-nums text-rd-heading">{b.value}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-rd-panel">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${b.value}%`, background: b.color }}
                />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DiversityCard() {
  return (
    <div className="glow-card p-5">
      <CardHeader title="Diversity Overview" action="View details" />
      <div className="flex items-center gap-4">
        <div className="flex shrink-0 flex-col items-center">
          <div
            className="relative flex h-24 w-24 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(hsl(var(--rd-cyan)) ${DIVERSITY.index}%, hsl(var(--rd-panel)) 0)`,
            }}
          >
            <div className="flex h-[76px] w-[76px] flex-col items-center justify-center rounded-full bg-rd-card">
              <span className="text-xl font-semibold tabular-nums text-rd-heading">
                {DIVERSITY.index}%
              </span>
              <span className="text-[11px] text-rd-muted">Diversity</span>
            </div>
          </div>
          <span className="mt-2 inline-flex items-center gap-1 text-xs">
            <Delta value={DIVERSITY.delta} />
            <span className="text-rd-muted">vs last month</span>
          </span>
        </div>
        <div className="min-w-0 flex-1 space-y-2.5">
          <Gender
            icon={User}
            label="Male"
            value={DIVERSITY.male.value}
            pct={DIVERSITY.male.pct}
            tone="text-rd-cyan"
          />
          <Gender
            icon={UserRound}
            label="Female"
            value={DIVERSITY.female.value}
            pct={DIVERSITY.female.pct}
            tone="text-rd-rose"
          />
        </div>
      </div>
      <div className="mt-4 border-t border-rd-border pt-3">
        <p className="mb-2 text-[11px] uppercase tracking-wide text-rd-muted">Top Nationalities</p>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {DIVERSITY.nationalities.map((n) => (
            <span key={n.label} className="flex items-center gap-1.5 text-xs text-rd-body">
              <span aria-hidden>{n.flag}</span>
              {n.label}
              <span className="font-medium text-rd-heading">{n.pct}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function Gender({
  icon: Icon,
  label,
  value,
  pct,
  tone,
}: {
  icon: typeof User;
  label: string;
  value: number;
  pct: string;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel ${tone}`}
      >
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-base font-semibold tabular-nums text-rd-heading">
          {value} <span className="text-xs font-normal text-rd-muted">({pct})</span>
        </p>
        <p className="text-xs text-rd-muted">{label}</p>
      </div>
    </div>
  );
}
