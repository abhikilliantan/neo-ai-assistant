"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ChevronRight,
  Code,
  type LucideIcon,
  LayoutGrid,
  Megaphone,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import Link from "next/link";
import type { DepartmentOverview, KpiRollup, NodeStatus, ProjectOverview } from "@neo/shared-types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { getCompanyOverview, listCompanies } from "@/services/overview";

// Department icon by the backend's lucide name; unknown/null → a neutral default.
const DEPT_ICONS: Record<string, LucideIcon> = {
  Megaphone,
  TrendingUp,
  Code,
  ShieldCheck,
  Users,
};
function deptIcon(name: string | null): LucideIcon {
  return (name && DEPT_ICONS[name]) || LayoutGrid;
}

const STATUS_LABEL: Record<NodeStatus, string> = {
  on_track: "On track",
  needs_attention: "Needs attention",
  not_connected: "Not connected",
};

export function OverviewView() {
  const companies = useQuery({ queryKey: ["companies"], queryFn: listCompanies });
  const [companyId, setCompanyId] = useState<string | null>(null);

  // Default to the first company once the list loads (and stay valid if it changes).
  useEffect(() => {
    const list = companies.data;
    if (list && list.length > 0 && !list.some((c) => c.id === companyId)) {
      setCompanyId(list[0].id);
    }
  }, [companies.data, companyId]);

  const overview = useQuery({
    queryKey: ["company-overview", companyId],
    queryFn: () => getCompanyOverview(companyId as string),
    enabled: !!companyId,
  });

  return (
    <div className="space-y-6">
      {/* Header: company switcher + freshness */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {companies.isLoading && (
            <div className="h-8 w-40 animate-pulse rounded-control bg-glass" />
          )}
          {companies.data?.map((c) => (
            <button
              key={c.id}
              onClick={() => setCompanyId(c.id)}
              className={cn(
                "rounded-control px-3 py-1.5 text-sm font-medium transition-colors",
                c.id === companyId
                  ? "glass-hi text-foreground"
                  : "text-muted-foreground hover:bg-glass hover:text-foreground",
              )}
            >
              {c.name}
            </button>
          ))}
          {companies.data?.length === 0 && (
            <span className="text-sm text-muted-foreground">No companies yet</span>
          )}
        </div>
        <span className="text-sm text-muted-foreground">
          Updated {overview.data ? formatRelative(overview.data.updated_at) : "just now"}
        </span>
      </div>

      {overview.isError && (
        <p className="text-sm text-danger">Couldn’t load the overview. Try again.</p>
      )}

      <KpiStrip kpis={overview.data?.kpis} loading={overview.isLoading} />

      {/* Company → Department → Project */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">
          Company <ChevronRight className="inline h-3.5 w-3.5" /> Department{" "}
          <ChevronRight className="inline h-3.5 w-3.5" /> Project
        </h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {overview.isLoading &&
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-56 animate-pulse rounded-card bg-glass" />
            ))}
          {overview.data?.departments.map((d) => (
            <DepartmentCard key={d.id} dept={d} />
          ))}
        </div>
      </section>

      <PlaceholderSection
        icon={Users}
        title="Team — who’s doing what"
        note="Lands in the next slice."
        body="A live table of people, their current projects, and workload will appear here once the Team slice ships."
      />
      <PlaceholderSection
        icon={Activity}
        title="Activity feed"
        note="Lands in the next slice."
        body="Recent changes across projects — status flips, new blockers, completions — will stream here once the Activity slice ships."
      />
    </div>
  );
}

// --- KPI strip ---------------------------------------------------------------

function KpiStrip({ kpis, loading }: { kpis?: KpiRollup; loading: boolean }) {
  const tiles: { label: string; value: number | undefined }[] = [
    { label: "Active projects", value: kpis?.active_projects },
    { label: "Scheduled this week", value: kpis?.scheduled_this_week },
    { label: "Open actions", value: kpis?.open_actions },
    { label: "Blocked", value: kpis?.blocked },
  ];
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-card border border-glass-border bg-glass p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t.label}
          </div>
          <div className="mt-2 flex items-end justify-between gap-2">
            <span className="text-3xl font-semibold tabular-nums text-foreground">
              {loading || t.value === undefined ? "—" : t.value}
            </span>
            {/* Placeholder sparkline — real trend arrives with the snapshot slice. */}
            <SparklinePlaceholder />
          </div>
          {/* Placeholder delta until week-over-week snapshots exist. */}
          <div className="mt-1 text-xs text-faint">— vs last week</div>
        </div>
      ))}
    </div>
  );
}

function SparklinePlaceholder() {
  return (
    <svg viewBox="0 0 64 20" className="h-5 w-16 text-faint/50" aria-hidden fill="none">
      <polyline
        points="0,15 12,10 24,13 36,6 48,9 64,4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// --- Department hero card ----------------------------------------------------

function DepartmentCard({ dept }: { dept: DepartmentOverview }) {
  const Icon = deptIcon(dept.icon);
  const connected = dept.status !== "not_connected";

  return (
    <div className="flex flex-col rounded-card border border-glass-border bg-glass p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-control bg-accent-grad text-on-accent shadow-glow">
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <div className="font-semibold text-foreground">{dept.name}</div>
            <div className="text-xs text-muted-foreground">
              {dept.project_count} project{dept.project_count === 1 ? "" : "s"}
            </div>
          </div>
        </div>
        <StatusPill status={dept.status} />
      </div>

      {connected ? (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <Stat label="Projects" value={dept.connected_project_count} />
            <Stat
              label="Progress"
              value={dept.progress_pct === null ? "—" : `${dept.progress_pct}%`}
            />
            <Stat label="Open" value={dept.open_actions ?? "—"} />
          </div>
          <div className="mt-4 space-y-3">
            {dept.projects.map((p) => (
              <ProjectRow key={p.id} project={p} />
            ))}
          </div>
          <div className="mt-4 pt-1">
            {/* View all → the Projects surface (next slice). Disabled until then. */}
            <button
              disabled
              title="Full project list arrives in the Projects slice"
              className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground opacity-60"
            >
              View all <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </>
      ) : (
        <NotConnected />
      )}
    </div>
  );
}

function NotConnected() {
  return (
    <div className="mt-4 flex flex-1 flex-col items-start justify-center gap-3 rounded-control border border-dashed border-glass-border-strong px-4 py-6">
      <p className="text-sm text-muted-foreground">
        No data source connected — metrics stay hidden until this department’s projects link a
        dataset.
      </p>
      <Link
        href="/datasets"
        className="inline-flex items-center gap-1 rounded-control bg-accent-grad px-3 py-1.5 text-sm font-semibold text-on-accent shadow-glow transition hover:brightness-110"
      >
        Connect now <ChevronRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-control bg-glass px-2 py-2">
      <div className="text-lg font-semibold tabular-nums text-foreground">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  );
}

function ProjectRow({ project }: { project: ProjectOverview }) {
  const pct = project.progress_pct;
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate text-foreground">{project.name}</span>
        <span className="shrink-0 tabular-nums text-muted-foreground">
          {pct === null ? "—" : `${pct}%`}
          {project.open_actions ? ` · ${project.open_actions} open` : ""}
        </span>
      </div>
      <ProgressBar project={project} />
    </div>
  );
}

function ProgressBar({ project }: { project: ProjectOverview }) {
  // green / amber / red by health: blocked → red, low progress → amber, else green.
  // Not connected → an empty muted track (no fabricated fill).
  const pct = project.progress_pct ?? 0;
  const color =
    project.status === "not_connected"
      ? "bg-muted"
      : (project.blocked_actions ?? 0) > 0
        ? "bg-danger"
        : pct < 50
          ? "bg-warn"
          : "bg-success";
  return (
    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-glass-hi">
      <div
        className={cn("h-full rounded-full transition-all", color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function StatusPill({ status }: { status: NodeStatus }) {
  const styles: Record<NodeStatus, string> = {
    on_track: "bg-success/15 text-success",
    needs_attention: "bg-warn/15 text-warn",
    not_connected: "bg-muted text-muted-foreground",
  };
  return (
    <span className={cn("shrink-0 rounded-full px-2.5 py-1 text-xs font-medium", styles[status])}>
      {STATUS_LABEL[status]}
    </span>
  );
}

// --- labelled placeholders (next slices) -------------------------------------

function PlaceholderSection({
  icon: Icon,
  title,
  note,
  body,
}: {
  icon: LucideIcon;
  title: string;
  note: string;
  body: string;
}) {
  return (
    <section className="rounded-card border border-dashed border-glass-border-strong bg-glass p-5">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h2 className="font-semibold text-foreground">{title}</h2>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
          {note}
        </span>
      </div>
      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{body}</p>
    </section>
  );
}
