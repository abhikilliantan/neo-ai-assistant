"use client";

import { Delta, MiniBars, SampleTag, Sparkline } from "@/features/redesign/components";
import { INSIGHTS } from "./data";

export function MeetingInsights() {
  return (
    <div className="glow-card p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">Meeting Insights</h3>
          <span className="text-xs text-rd-muted">(AI Generated)</span>
          <SampleTag />
        </div>
        <span className="text-xs font-medium text-rd-cyan">View all insights →</span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {INSIGHTS.map((ins) => (
          <div
            key={ins.title}
            className="rounded-control border border-rd-border bg-rd-panel/40 p-4"
          >
            <p className="text-sm font-semibold text-rd-heading">{ins.title}</p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-base font-semibold tabular-nums text-rd-heading">
                {ins.value}
              </span>
              {ins.delta !== undefined && <Delta value={ins.delta} />}
            </div>
            <p className="text-xs text-rd-muted">{ins.sub}</p>

            <div className="mt-3">
              {ins.chart === "spark-green" && (
                <Sparkline data={ins.data} color="green" height={48} />
              )}
              {ins.chart === "spark-amber" && (
                <Sparkline data={ins.data} color="amber" height={48} />
              )}
              {ins.chart === "bars-violet" && (
                <MiniBars data={ins.data} color="violet" height={48} />
              )}
              {ins.chart === "ring" && ins.ringPct != null && (
                <div className="flex justify-center">
                  <div
                    className="relative flex h-14 w-14 items-center justify-center rounded-full"
                    style={{
                      background: `conic-gradient(hsl(var(--rd-green)) ${ins.ringPct}%, hsl(var(--rd-panel)) 0)`,
                    }}
                  >
                    <span className="flex h-[42px] w-[42px] items-center justify-center rounded-full bg-rd-card text-xs font-semibold tabular-nums text-rd-heading">
                      {ins.ringPct}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
