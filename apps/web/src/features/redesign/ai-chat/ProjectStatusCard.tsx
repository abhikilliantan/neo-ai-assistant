"use client";

import { ChevronRight, ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";
import { RingGauge } from "@/features/redesign/components";

// --- Data shape ------------------------------------------------------------
// A project_analyst answer is rendered as this structured card ONLY when the
// model returns a machine-readable block matching this shape. Otherwise the
// caller falls back to plain markdown — we never fabricate these fields.
export type ProjectRisk = { label: string; level: "high" | "medium" | "low" };

export type ProjectStatusData = {
  name: string;
  status: "on-track" | "at-risk" | "delayed";
  progress: number;
  progressDelta?: string;
  phase?: string;
  startDate?: string;
  targetGoLive?: string;
  daysRemaining?: number;
  prediction?: string;
  modules?: { completed: number; total: number };
  teamActive?: number;
  risksHigh?: number;
  issuesOpen?: number;
  highlights?: string[];
  risks?: ProjectRisk[];
};

const STATUS_TAG: Record<ProjectStatusData["status"], { label: string; cls: string }> = {
  "on-track": { label: "On Track", cls: "border-rd-green/40 bg-rd-green/10 text-rd-green" },
  "at-risk": { label: "At Risk", cls: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber" },
  delayed: { label: "Delayed", cls: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose" },
};

const RISK_TAG: Record<ProjectRisk["level"], { label: string; cls: string }> = {
  high: { label: "High", cls: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose" },
  medium: { label: "Medium", cls: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber" },
  low: { label: "Low", cls: "border-rd-green/40 bg-rd-green/10 text-rd-green" },
};

// --- Parser ----------------------------------------------------------------
// ponytail: opportunistic, not a general NL parser. We only "upgrade" an answer
// to the styled card when the model hands us a ```json fence whose object has
// at least name + progress + status. Anything short of that → return null and
// the caller renders the real markdown. Zero invented data.
export function parseProjectStatus(content: string): ProjectStatusData | null {
  const fence = content.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (!fence) return null;
  let raw: unknown;
  try {
    raw = JSON.parse(fence[1].trim());
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const o = raw as Record<string, unknown>;
  const status = o.status;
  if (
    typeof o.name !== "string" ||
    typeof o.progress !== "number" ||
    (status !== "on-track" && status !== "at-risk" && status !== "delayed")
  ) {
    return null;
  }
  return raw as ProjectStatusData;
}

// The text left over once the ```json block is removed (the model's prose).
export function stripStatusBlock(content: string): string {
  return content.replace(/```(?:json)?\s*[\s\S]*?```/i, "").trim();
}

// --- Card ------------------------------------------------------------------
export function ProjectStatusCard({ data }: { data: ProjectStatusData }) {
  const tag = STATUS_TAG[data.status];

  return (
    <div className="glow-card overflow-hidden p-0">
      {/* Title + status */}
      <div className="flex items-center justify-between gap-3 border-b border-rd-border px-5 py-4">
        <h3 className="truncate text-base font-semibold text-rd-heading">{data.name}</h3>
        <span className="flex items-center gap-1.5">
          <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-medium", tag.cls)}>
            {tag.label}
          </span>
          <ChevronRight className="h-4 w-4 text-rd-muted" aria-hidden />
        </span>
      </div>

      {/* Progress ring + phase/dates */}
      <div className="grid grid-cols-1 gap-5 px-5 py-5 sm:grid-cols-[auto_minmax(0,1fr)]">
        <div className="flex flex-col items-center gap-1">
          <p className="mb-1 self-start text-xs text-rd-muted">Overall Progress</p>
          <RingGauge value={data.progress} size={132} />
          {data.progressDelta && (
            <p className="text-xs font-medium text-rd-green">↑ {data.progressDelta}</p>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-4 self-center sm:grid-cols-3">
          <Field label="Phase" value={data.phase} />
          <Field label="Start Date" value={data.startDate} />
          <Field label="Target Go-Live" value={data.targetGoLive} />
          <Field
            label="Days Remaining"
            value={data.daysRemaining != null ? `${data.daysRemaining}` : undefined}
            sub={data.daysRemaining != null ? "days" : undefined}
          />
          <Field label="AI Prediction" value={data.prediction} valueClass="text-rd-green" wide />
        </dl>
      </div>

      {/* Stat tiles */}
      {(data.modules ||
        data.teamActive != null ||
        data.risksHigh != null ||
        data.issuesOpen != null) && (
        <div className="grid grid-cols-2 gap-3 px-5 pb-5 sm:grid-cols-4">
          {data.modules && (
            <StatTile
              label="Modules"
              value={`${data.modules.completed} / ${data.modules.total}`}
              sub="Completed"
            />
          )}
          {data.teamActive != null && (
            <StatTile label="Team" value={`${data.teamActive}`} sub="Active Members" />
          )}
          {data.risksHigh != null && (
            <StatTile label="Risks" value={`${data.risksHigh}`} sub="High Priority" tone="amber" />
          )}
          {data.issuesOpen != null && (
            <StatTile label="Issues" value={`${data.issuesOpen}`} sub="Open" tone="rose" />
          )}
        </div>
      )}

      {/* Highlights + risks */}
      {(data.highlights?.length || data.risks?.length) && (
        <div className="grid grid-cols-1 gap-4 border-t border-rd-border px-5 py-5 lg:grid-cols-2">
          {data.highlights?.length ? (
            <div className="rounded-control border border-rd-border bg-rd-panel/50 p-4">
              <p className="mb-3 text-sm font-semibold text-rd-heading">Key Highlights</p>
              <ul className="space-y-2">
                {data.highlights.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-rd-body">
                    <span className="mt-0.5 text-rd-green" aria-hidden>
                      ✓
                    </span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {data.risks?.length ? (
            <div className="rounded-control border border-rd-border bg-rd-panel/50 p-4">
              <p className="mb-3 text-sm font-semibold text-rd-heading">Top Risks</p>
              <ul className="space-y-2.5">
                {data.risks.map((r, i) => (
                  <li key={i} className="flex items-start justify-between gap-2 text-sm">
                    <span className="flex items-start gap-2 text-rd-body">
                      <span className="mt-0.5 text-rd-rose" aria-hidden>
                        +
                      </span>
                      <span>{r.label}</span>
                    </span>
                    <span
                      className={cn(
                        "shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                        RISK_TAG[r.level].cls,
                      )}
                    >
                      {RISK_TAG[r.level].label}
                    </span>
                  </li>
                ))}
              </ul>
              <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-rd-cyan">
                View full risk register <ExternalLink className="h-3 w-3" aria-hidden />
              </span>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  sub,
  valueClass,
  wide,
}: {
  label: string;
  value?: string;
  sub?: string;
  valueClass?: string;
  wide?: boolean;
}) {
  if (!value) return null;
  return (
    <div className={cn(wide && "col-span-2 sm:col-span-1")}>
      <dt className="text-xs text-rd-muted">{label}</dt>
      <dd className={cn("mt-0.5 text-sm font-medium text-rd-heading", valueClass)}>
        {value}
        {sub && <span className="ml-1 text-xs font-normal text-rd-muted">{sub}</span>}
      </dd>
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "amber" | "rose";
}) {
  const valueTone =
    tone === "amber" ? "text-rd-amber" : tone === "rose" ? "text-rd-rose" : "text-rd-heading";
  return (
    <div className="rounded-control border border-rd-border bg-rd-panel/50 p-3">
      <p className="text-xs text-rd-muted">{label}</p>
      <p className={cn("mt-1 text-xl font-semibold tabular-nums", valueTone)}>{value}</p>
      <p className="text-[11px] text-rd-muted">{sub}</p>
    </div>
  );
}
