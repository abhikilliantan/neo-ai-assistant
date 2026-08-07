"use client";

import { useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  Globe,
  Linkedin,
  Mail,
  Presentation,
  Search,
  Youtube,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Funnel, SampleTag, Sparkline } from "@/features/redesign/components";
import { CAMPAIGNS, CHANNELS, FUNNEL, FUNNEL_OVERALL } from "./data";

const CHANNEL_ICON: Record<string, LucideIcon> = {
  linkedin: Linkedin,
  website: Globe,
  email: Mail,
  search: Search,
  youtube: Youtube,
  webinar: Presentation,
  events: CalendarDays,
};

export function MarketingMiddle() {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
      <ChannelCard />
      <FunnelCard />
      <CampaignCard />
    </div>
  );
}

function CardHead({ title, note }: { title: string; note?: string }) {
  const [period, setPeriod] = useState("This Month");
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-rd-heading">
          {title}
          {note && <span className="ml-1 font-normal text-rd-muted">{note}</span>}
        </h3>
        <SampleTag />
      </div>
      <select
        value={period}
        onChange={(e) => setPeriod(e.target.value)}
        aria-label="Period"
        className="h-8 rounded-control border border-rd-border bg-rd-panel/50 px-2 text-xs text-rd-body focus:border-rd-border-hover focus:outline-none"
      >
        {["This Month", "This Quarter", "This Year"].map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function RoiCell({ roi, spark }: { roi: number; spark: number[] }) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      <Sparkline data={spark} color="green" height={18} className="w-10" />
      <span className="w-12 text-right text-xs font-semibold tabular-nums text-rd-green">
        {roi}%
      </span>
    </div>
  );
}

function ChannelCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Channel Performance" />
      <div className="-mx-2 flex-1 overflow-x-auto">
        <table className="w-full min-w-[380px] text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-rd-muted">
              <th className="px-2 py-2 font-medium">Channel</th>
              <th className="px-2 py-2 text-right font-medium">Visitors</th>
              <th className="px-2 py-2 text-right font-medium">Leads</th>
              <th className="px-2 py-2 text-right font-medium">Conv.</th>
              <th className="px-2 py-2 text-right font-medium">ROI</th>
            </tr>
          </thead>
          <tbody>
            {CHANNELS.map((c) => {
              const Icon = CHANNEL_ICON[c.icon];
              return (
                <tr key={c.name} className="border-t border-rd-border/60">
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 shrink-0 text-rd-cyan" aria-hidden />
                      <span className="truncate text-sm text-rd-heading">{c.name}</span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                    {c.visitors}
                  </td>
                  <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                    {c.leads}
                  </td>
                  <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-heading">
                    {c.convRate}
                  </td>
                  <td className="px-2 py-2.5">
                    <RoiCell roi={c.roi} spark={c.spark} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <FooterLink label="View full channel report" />
    </div>
  );
}

function FunnelCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Leads Funnel" note="(MTD)" />
      <Funnel rows={FUNNEL} pctHeader="Conv." className="flex-1" />
      <div className="mt-4 flex items-center justify-between border-t border-rd-border pt-4">
        <span className="text-xs text-rd-muted">Overall Conversion Rate</span>
        <span className="text-sm font-semibold tabular-nums text-rd-green">{FUNNEL_OVERALL}</span>
      </div>
    </div>
  );
}

function CampaignCard() {
  return (
    <div className="glow-card flex flex-col p-5">
      <CardHead title="Campaign Performance" />
      <div className="-mx-2 flex-1 overflow-x-auto">
        <table className="w-full min-w-[340px] text-left">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-rd-muted">
              <th className="px-2 py-2 font-medium">Campaign</th>
              <th className="px-2 py-2 text-right font-medium">Spend</th>
              <th className="px-2 py-2 text-right font-medium">Leads</th>
              <th className="px-2 py-2 text-right font-medium">ROI</th>
            </tr>
          </thead>
          <tbody>
            {CAMPAIGNS.map((c) => (
              <tr key={c.name} className="border-t border-rd-border/60">
                <td className="px-2 py-2.5">
                  <span className="block max-w-[150px] truncate text-sm text-rd-heading">
                    {c.name}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {c.spend}
                </td>
                <td className="px-2 py-2.5 text-right text-sm tabular-nums text-rd-body">
                  {c.leads}
                </td>
                <td className="px-2 py-2.5">
                  <RoiCell roi={c.roi} spark={c.spark} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <FooterLink label="View all campaigns" />
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
