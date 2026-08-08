"use client";

import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { AvatarStack, Delta, Donut, SampleTag } from "@/features/redesign/components";
import { cn } from "@/lib/cn";
import { DEAL_HEALTH, REGIONS, REPS } from "./data";

export function SalesBottom() {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <PerformanceCard />
      <RegionCard />
      <DealHealthCard />
    </div>
  );
}

function CardHead({
  title,
  selects,
}: {
  title: string;
  selects?: { value: string; onChange: (v: string) => void; options: string[] }[];
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">{title}</h3>
        <SampleTag />
      </div>
      {selects && (
        <div className="flex items-center gap-2">
          {selects.map((s, i) => (
            <MiniSelect key={i} {...s} />
          ))}
        </div>
      )}
    </div>
  );
}

function PerformanceCard() {
  const [period, setPeriod] = useState("This Month");
  const [rep, setRep] = useState("All Reps");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Sales Performance"
        selects={[
          {
            value: period,
            onChange: setPeriod,
            options: ["This Month", "This Quarter", "This Year"],
          },
          { value: rep, onChange: setRep, options: ["All Reps", "Directors", "Executives"] },
        ]}
      />
      <div className="-mx-2 flex-1 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-rd-muted">
              <th className="px-2 py-2 font-medium">Rep</th>
              <th className="px-2 py-2 text-right font-medium">Deals</th>
              <th className="px-2 py-2 text-right font-medium">Pipeline</th>
              <th className="px-2 py-2 text-right font-medium">Closed Won</th>
              <th className="px-2 py-2 text-right font-medium">Win Rate</th>
              <th className="px-2 py-2 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {REPS.map((r) => (
              <tr key={r.name} className="border-t border-rd-border/60">
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <AvatarStack names={[r.name]} size={30} />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-rd-heading">{r.name}</p>
                      <p className="truncate text-xs text-rd-muted">{r.role}</p>
                    </div>
                  </div>
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {r.deals}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-heading">
                  {r.pipeline}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-heading">
                  {r.won}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {r.winRate}
                </td>
                <td className="px-2 py-2.5 text-right">
                  <span className="inline-flex min-w-8 justify-center rounded-full border border-rd-green/40 bg-rd-green/10 px-2 py-0.5 text-xs font-semibold tabular-nums text-rd-green">
                    {r.score}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <FooterLink label="View full leaderboard" />
    </div>
  );
}

function RegionCard() {
  const [period, setPeriod] = useState("This Month");
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Sales by Region"
        selects={[{ value: period, onChange: setPeriod, options: ["This Month", "This Quarter"] }]}
      />
      {/* ponytail: stylized map backdrop (glow dots on a faint grid), not a real
          geo map — the region list below carries the numbers. */}
      <div className="relative mb-4 h-32 overflow-hidden rounded-card border border-rd-border bg-rd-panel/40">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage: "radial-gradient(hsl(var(--rd-border)) 1px, transparent 1px)",
            backgroundSize: "14px 14px",
          }}
          aria-hidden
        />
        {[
          { top: "38%", left: "55%" },
          { top: "50%", left: "58%" },
          { top: "44%", left: "48%" },
          { top: "30%", left: "72%" },
          { top: "62%", left: "40%" },
        ].map((p, i) => (
          <span
            key={i}
            className="absolute h-2 w-2 rounded-full bg-rd-cyan"
            style={{ top: p.top, left: p.left, boxShadow: "0 0 8px 2px hsl(var(--rd-cyan) / 0.6)" }}
            aria-hidden
          />
        ))}
      </div>
      <ul className="flex-1 space-y-2.5">
        {REGIONS.map((r) => (
          <li key={r.label} className="flex items-center gap-2 text-sm">
            <span className="min-w-0 flex-1 truncate text-rd-body">{r.label}</span>
            <span className="shrink-0 tabular-nums text-rd-heading">{r.value}</span>
            <Delta value={r.delta} className="w-14 justify-end" />
          </li>
        ))}
      </ul>
    </div>
  );
}

function DealHealthCard() {
  const [scope, setScope] = useState("All Deals");
  const { total, slices, insight } = DEAL_HEALTH;
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead
        title="Deal Health"
        selects={[{ value: scope, onChange: setScope, options: ["All Deals", "My Deals"] }]}
      />
      <div className="flex items-center gap-4">
        <Donut
          data={slices.map((s) => ({ label: s.label, value: s.count, color: s.color }))}
          centerValue={String(total)}
          centerLabel="Total Deals"
          size={128}
          className="shrink-0"
        />
        <ul className="min-w-0 flex-1 space-y-2">
          {slices.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-sm">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-rd-body">{s.label}</span>
              <span className="shrink-0 tabular-nums text-rd-heading">{s.count}</span>
              <span className="w-14 shrink-0 text-right tabular-nums text-rd-muted">({s.pct})</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-4 rounded-card border border-rd-border bg-rd-panel/40 p-3">
        <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-rd-cyan">
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          AI Insight
        </div>
        <p className="text-xs text-rd-body">{insight}</p>
      </div>
      <FooterLink label="View at-risk deals" />
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

function MiniSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Filter"
      className={cn(
        "h-8 rounded-control border border-rd-border bg-rd-panel/50 px-2 text-xs text-rd-body",
        "focus:border-rd-border-hover focus:outline-none",
      )}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
