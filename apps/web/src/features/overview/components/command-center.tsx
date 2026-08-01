"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Bell,
  Briefcase,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Code2,
  FileBarChart,
  FileText,
  FolderKanban,
  Home,
  LayoutGrid,
  Link2,
  Lock,
  type LucideIcon,
  Megaphone,
  Moon,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  TrendingUp,
  TriangleAlert,
  Users,
} from "lucide-react";
import type {
  CompanyOverview,
  CompanySummary,
  DepartmentOverview,
  NodeStatus,
  ProjectOverview,
} from "@neo/shared-types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { logout as apiLogout } from "@/services/auth";
import { getCompanyOverview, listCompanies } from "@/services/overview";
import { SAMPLE_ACTIVITY, SAMPLE_TEAM } from "@/features/overview/sample-data";
import { getStoredRefreshToken, useSessionStore } from "@/store/session";

// --- shared style tokens (explicit light/dark to match the mock exactly) -----

const CARD =
  "rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.05)] dark:border-white/[0.06] dark:bg-[#14161b] dark:shadow-none";

const TINT: Record<string, string> = {
  blue: "bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300",
  violet: "bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300",
  emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300",
  indigo: "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300",
  amber: "bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300",
  rose: "bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300",
  red: "bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300",
};

const DEPT_META: Record<string, { icon: LucideIcon; tint: string }> = {
  Marketing: { icon: Megaphone, tint: "blue" },
  Sales: { icon: TrendingUp, tint: "emerald" },
  Development: { icon: Code2, tint: "violet" },
  QA: { icon: ShieldCheck, tint: "indigo" },
  "People/HR": { icon: Users, tint: "rose" },
  "People / HR": { icon: Users, tint: "rose" },
};
function deptMeta(name: string): { icon: LucideIcon; tint: string } {
  return DEPT_META[name] ?? { icon: LayoutGrid, tint: "blue" };
}

const AVATAR_TINTS = ["blue", "violet", "emerald", "amber", "rose", "indigo"];

// --- entry -------------------------------------------------------------------

export function CommandCenter() {
  const companies = useQuery({ queryKey: ["companies"], queryFn: listCompanies });
  const [companyId, setCompanyId] = useState<string | null>(null);

  // Pin the primary company (Skillmind) first, rest alphabetical — deterministic
  // order the API doesn't guarantee.
  const ordered = useMemo(() => {
    const list = [...(companies.data ?? [])];
    return list.sort((a, b) => {
      const pa = a.name.startsWith("Skillmind") ? 0 : 1;
      const pb = b.name.startsWith("Skillmind") ? 0 : 1;
      return pa - pb || a.name.localeCompare(b.name);
    });
  }, [companies.data]);

  useEffect(() => {
    if (ordered.length > 0 && !ordered.some((c) => c.id === companyId)) {
      setCompanyId(ordered[0].id);
    }
  }, [ordered, companyId]);

  const overview = useQuery({
    queryKey: ["company-overview", companyId],
    queryFn: () => getCompanyOverview(companyId as string),
    enabled: !!companyId,
  });

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-[#f5f6f8] text-slate-900 dark:bg-[#0a0b0e] dark:text-slate-100">
      <CommandSidebar companies={ordered} selectedId={companyId} onSelect={setCompanyId} />
      <div className="flex min-w-0 flex-1 flex-col">
        <CommandTopbar
          companyName={overview.data?.company.name ?? "—"}
          updatedAt={overview.data?.updated_at}
          onRefresh={() => overview.refetch()}
          refreshing={overview.isFetching}
        />
        <main className="min-w-0 flex-1 overflow-auto px-5 py-5 md:px-7 md:py-6">
          <div className="mx-auto max-w-[1400px] space-y-6">
            {overview.isError && (
              <p className="text-sm text-red-600 dark:text-red-400">
                Couldn’t load this company’s overview. Try again.
              </p>
            )}
            <KpiStrip data={overview.data} loading={overview.isLoading} />
            <DepartmentsSection data={overview.data} loading={overview.isLoading} />
            <div className="grid gap-6 xl:grid-cols-3">
              <TeamTable />
              <ActivityFeed />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

// --- sidebar -----------------------------------------------------------------

const NAV = [
  { label: "Overview", icon: Home, active: true },
  { label: "Projects", icon: FolderKanban, active: false },
  { label: "Team", icon: Users, active: false },
  { label: "Activity", icon: Activity, active: false },
  { label: "Reports", icon: FileBarChart, active: false },
] as const;

function CommandSidebar({
  companies,
  selectedId,
  onSelect,
}: {
  companies: CompanySummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const user = useSessionStore((s) => s.user);
  const clearSession = useSessionStore((s) => s.clearSession);
  const router = useRouter();

  async function handleLogout() {
    const token = getStoredRefreshToken();
    if (token) {
      try {
        await apiLogout(token);
      } catch {
        /* best-effort */
      }
    }
    clearSession();
    router.replace("/login");
  }

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex dark:border-white/[0.06] dark:bg-[#0c0d11]">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-sky-400 to-blue-600 text-white shadow-sm">
          <span className="text-lg font-black leading-none">N</span>
        </span>
        <div className="leading-tight">
          <div className="text-[15px] font-extrabold tracking-tight text-blue-600 dark:text-blue-400">
            NEO
          </div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Command Center
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {/* Companies */}
        <SectionLabel>Companies</SectionLabel>
        <div className="space-y-1">
          {companies.map((c, i) => {
            const selected = c.id === selectedId;
            return (
              <button
                key={c.id}
                onClick={() => onSelect(c.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-sm transition-colors",
                  selected
                    ? "bg-blue-50 font-semibold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.04]",
                )}
              >
                <span
                  className={cn(
                    "grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs font-bold",
                    TINT[AVATAR_TINTS[i % AVATAR_TINTS.length]],
                  )}
                >
                  {c.name.charAt(0)}
                </span>
                <span className="truncate">{c.name}</span>
                {selected && <BadgeCheck className="ml-auto h-4 w-4 shrink-0 text-blue-500" />}
              </button>
            );
          })}
          {companies.length === 0 && (
            <div className="px-2.5 py-2 text-sm text-slate-400">No companies yet</div>
          )}
        </div>

        {/* Navigation */}
        <SectionLabel className="mt-5">Navigation</SectionLabel>
        <nav className="space-y-1">
          {NAV.map(({ label, icon: Icon, active }) => (
            <button
              key={label}
              disabled={!active}
              title={active ? undefined : "Coming in a later slice"}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-blue-50 font-semibold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
                  : "text-slate-500 hover:bg-slate-50 disabled:hover:bg-transparent dark:text-slate-400 dark:hover:bg-white/[0.04]",
              )}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Ask Neo */}
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-white/[0.06] dark:bg-white/[0.03]">
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="text-sm font-semibold">Neo AI Chief of Staff</span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            I’m monitoring your business across all companies. Ask me anything.
          </p>
          <button
            className="mt-3 flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-blue-600 transition hover:border-blue-200 dark:border-white/10 dark:bg-white/[0.04] dark:text-blue-300"
            title="Ask Neo (chat) — wiring lands with the assistant slice"
          >
            Ask Neo <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* CEO footer */}
      <button
        onClick={handleLogout}
        title="Sign out"
        className="flex items-center gap-3 border-t border-slate-200 px-4 py-3 text-left transition hover:bg-slate-50 dark:border-white/[0.06] dark:hover:bg-white/[0.04]"
      >
        <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-xs font-bold text-white">
          {initials(user?.email)}
        </span>
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-sm font-semibold">
            {user?.email?.split("@")[0] ?? "Account"}
          </span>
          <span className="block text-xs text-slate-400">CEO</span>
        </span>
        <ChevronDown className="ml-auto h-4 w-4 text-slate-400" />
      </button>
    </aside>
  );
}

function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "px-2.5 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400",
        className,
      )}
    >
      {children}
    </div>
  );
}

// --- top bar -----------------------------------------------------------------

function CommandTopbar({
  companyName,
  updatedAt,
  onRefresh,
  refreshing,
}: {
  companyName: string;
  updatedAt?: string;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/80 px-5 backdrop-blur md:px-7 dark:border-white/[0.06] dark:bg-[#0c0d11]/80">
      <h1 className="flex items-center gap-2 text-lg font-bold tracking-tight md:text-xl">
        <span className="truncate">{companyName}</span>
        <CheckCircle2 className="h-5 w-5 shrink-0 fill-blue-500 text-white dark:text-[#0c0d11]" />
      </h1>
      <div className="hidden items-center gap-1.5 text-sm text-slate-500 sm:flex dark:text-slate-400">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        Updated {updatedAt ? formatRelative(updatedAt) : "just now"}
        <button
          onClick={onRefresh}
          aria-label="Refresh"
          className="ml-1 rounded-md p-1 text-slate-400 transition hover:text-slate-700 dark:hover:text-slate-200"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
        </button>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <ThemeSegmented />
        <button className="hidden items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 md:flex dark:border-white/10 dark:text-slate-300">
          <CalendarDays className="h-4 w-4" /> Today <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <IconButton label="Search">
          <Search className="h-[18px] w-[18px]" />
        </IconButton>
        <div className="relative">
          <IconButton label="Notifications">
            <Bell className="h-[18px] w-[18px]" />
          </IconButton>
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-blue-500 ring-2 ring-white dark:ring-[#0c0d11]" />
        </div>
      </div>
    </header>
  );
}

function IconButton({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <button
      aria-label={label}
      className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-50 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/[0.05]"
    >
      {children}
    </button>
  );
}

function ThemeSegmented() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  const seg =
    "flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-sm font-medium transition-colors";
  return (
    <div className="flex items-center gap-1 rounded-xl border border-slate-200 p-0.5 dark:border-white/10">
      <button
        onClick={() => setTheme("light")}
        className={cn(seg, !dark ? "bg-blue-50 text-blue-700" : "text-slate-400")}
      >
        <Sun className="h-4 w-4" /> Light
      </button>
      <button
        onClick={() => setTheme("dark")}
        className={cn(seg, dark ? "bg-white/10 text-white" : "text-slate-500")}
      >
        <Moon className="h-4 w-4" /> Dark
      </button>
    </div>
  );
}

// --- KPI strip ---------------------------------------------------------------

function KpiStrip({ data, loading }: { data?: CompanyOverview; loading: boolean }) {
  const k = data?.kpis;
  const tiles = [
    {
      label: "Active projects",
      value: k?.active_projects,
      tint: "blue",
      icon: Briefcase,
      up: true,
    },
    {
      label: "Scheduled this week",
      value: k?.scheduled_this_week,
      tint: "violet",
      icon: CalendarDays,
      up: true,
    },
    { label: "Open actions", value: k?.open_actions, tint: "amber", icon: ClipboardList, up: true },
    { label: "Blocked", value: k?.blocked, tint: "red", icon: Lock, up: false },
  ] as const;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className={cn(CARD, "flex items-center gap-4 p-4")}>
          <span
            className={cn("grid h-12 w-12 shrink-0 place-items-center rounded-xl", TINT[t.tint])}
          >
            <t.icon className="h-6 w-6" />
          </span>
          <div className="min-w-0">
            <div className="text-2xl font-bold tabular-nums leading-none">
              {loading || t.value === undefined ? "—" : t.value}
            </div>
            <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t.label}</div>
            {/* Placeholder trend — real delta lands with the snapshot slice. */}
            <div
              className="mt-1 flex items-center gap-1 text-xs text-slate-400"
              title="Trend arrives with the snapshot slice"
            >
              <ArrowUpRight
                className={cn("h-3.5 w-3.5", t.up ? "text-emerald-500" : "text-red-500")}
              />
              vs last week
            </div>
          </div>
          <Sparkline tint={t.tint} className="ml-auto hidden sm:block" />
        </div>
      ))}
    </div>
  );
}

const SPARK_STROKE: Record<string, string> = {
  blue: "text-blue-500",
  violet: "text-violet-500",
  amber: "text-amber-500",
  red: "text-red-500",
};

function Sparkline({ tint, className }: { tint: string; className?: string }) {
  // Decorative placeholder shape (no live series yet).
  return (
    <svg
      viewBox="0 0 80 32"
      className={cn("h-8 w-20", SPARK_STROKE[tint], className)}
      fill="none"
      aria-hidden
    >
      <polyline
        points="0,24 13,18 26,20 40,10 53,14 66,6 80,9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
    </svg>
  );
}

// --- departments -------------------------------------------------------------

function DepartmentsSection({ data, loading }: { data?: CompanyOverview; loading: boolean }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-sm font-medium text-slate-500 dark:text-slate-400">
          Company <ChevronRight className="h-3.5 w-3.5" /> Department{" "}
          <ChevronRight className="h-3.5 w-3.5" /> Project
        </h2>
        <button
          className="flex items-center gap-1 text-sm font-semibold text-blue-600 dark:text-blue-400"
          title="Full department list — Projects slice"
        >
          View all departments <ArrowRight className="h-4 w-4" />
        </button>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className={cn(CARD, "h-72 animate-pulse")} />
          ))}
        </div>
      ) : data && data.departments.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {data.departments.map((d) => (
            <DepartmentCard key={d.id} dept={d} />
          ))}
        </div>
      ) : (
        <div className={cn(CARD, "p-8 text-center text-sm text-slate-500 dark:text-slate-400")}>
          No departments yet for this company.
        </div>
      )}
    </section>
  );
}

function DepartmentCard({ dept }: { dept: DepartmentOverview }) {
  const { icon: Icon, tint } = deptMeta(dept.name);
  const connected = dept.status !== "not_connected";
  const openTint =
    dept.status === "needs_attention"
      ? "text-red-600 dark:text-red-400"
      : "text-slate-900 dark:text-slate-100";

  return (
    <div className={cn(CARD, "flex flex-col p-4")}>
      <div className="flex items-start justify-between">
        <span className={cn("grid h-11 w-11 place-items-center rounded-xl", TINT[tint])}>
          <Icon className="h-6 w-6" />
        </span>
        <MoreHorizontal className="h-5 w-5 text-slate-300 dark:text-slate-600" />
      </div>
      <div className="mt-2 text-[15px] font-bold">{dept.name}</div>
      <div className="mt-1.5">
        <StatusPill status={dept.status} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-1 text-center">
        <MiniStat value={connected ? dept.connected_project_count : "–"} label="Projects" />
        <MiniStat
          value={connected && dept.progress_pct !== null ? `${dept.progress_pct}%` : "–"}
          label="Progress"
        />
        <MiniStat
          value={connected && dept.open_actions !== null ? dept.open_actions : "–"}
          label="Open actions"
          valueClass={connected ? openTint : undefined}
        />
      </div>

      {connected ? (
        <>
          <div className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Projects
          </div>
          <div className="mt-2 flex-1 space-y-3">
            {dept.projects.map((p) => (
              <ProjectRow key={p.id} project={p} />
            ))}
          </div>
          <button
            className="mt-4 flex items-center gap-1 text-sm font-semibold text-blue-600 dark:text-blue-400"
            title="Full project list — Projects slice"
          >
            View all ({dept.project_count}) <ArrowRight className="h-4 w-4" />
          </button>
        </>
      ) : (
        <div className="mt-4 flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center dark:border-white/10">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-400 dark:bg-white/[0.06]">
            <Link2 className="h-5 w-5" />
          </span>
          <div className="text-sm font-semibold">Not connected</div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Connect your tools to unlock live data.
          </p>
          <a
            href="/datasets"
            className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-blue-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-blue-300"
          >
            Connect now
          </a>
        </div>
      )}
    </div>
  );
}

function MiniStat({
  value,
  label,
  valueClass,
}: {
  value: number | string;
  label: string;
  valueClass?: string;
}) {
  return (
    <div>
      <div className={cn("text-lg font-bold tabular-nums", valueClass)}>{value}</div>
      <div className="text-[11px] text-slate-400">{label}</div>
    </div>
  );
}

function ProjectRow({ project }: { project: ProjectOverview }) {
  const pct = project.progress_pct ?? 0;
  const barColor =
    (project.blocked_actions ?? 0) > 0 || pct < 50
      ? "bg-red-500"
      : pct < 75
        ? "bg-amber-500"
        : "bg-emerald-500";
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate text-slate-700 dark:text-slate-200">{project.name}</span>
        <span className="shrink-0 font-semibold tabular-nums text-slate-500 dark:text-slate-400">
          {project.progress_pct === null ? "–" : `${pct}%`}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-white/[0.07]">
        <div className={cn("h-full rounded-full", barColor)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: NodeStatus }) {
  const map: Record<NodeStatus, { label: string; cls: string }> = {
    on_track: {
      label: "On track",
      cls: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    },
    needs_attention: {
      label: "Needs attention",
      cls: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
    },
    not_connected: {
      label: "Not connected",
      cls: "bg-slate-100 text-slate-500 dark:bg-white/[0.06] dark:text-slate-400",
    },
  };
  const s = map[status];
  return (
    <span className={cn("rounded-md px-2 py-0.5 text-xs font-semibold", s.cls)}>{s.label}</span>
  );
}

// --- Team table (SAMPLE) -----------------------------------------------------

function TeamTable() {
  return (
    <div className="xl:col-span-2">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-bold">
          Team — Who’s doing what
          <SampleTag />
        </h2>
        <button className="flex items-center gap-1 text-sm font-semibold text-blue-600 dark:text-blue-400">
          View full team <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      <div className={cn(CARD, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400 dark:border-white/[0.06]">
                <th className="px-4 py-3 font-medium">Person</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Department</th>
                <th className="px-4 py-3 font-medium">Current task</th>
                <th className="px-4 py-3 font-medium">Project</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {SAMPLE_TEAM.map((m, i) => {
                const meta = deptMeta(m.department);
                return (
                  <tr
                    key={m.name}
                    className="border-b border-slate-100 last:border-0 dark:border-white/[0.04]"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span
                          className={cn(
                            "grid h-8 w-8 place-items-center rounded-full text-xs font-bold",
                            TINT[AVATAR_TINTS[i % AVATAR_TINTS.length]],
                          )}
                        >
                          {initials(m.name)}
                        </span>
                        <span className="font-medium">{m.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {m.role === "HOD" ? (
                        <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
                          HOD
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "grid h-6 w-6 place-items-center rounded-md",
                            TINT[meta.tint],
                          )}
                        >
                          <meta.icon className="h-3.5 w-3.5" />
                        </span>
                        <span className="text-slate-600 dark:text-slate-300">{m.department}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{m.task}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{m.project}</td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "rounded-md px-2 py-0.5 text-xs font-semibold",
                          m.status === "On track"
                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
                            : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
                        )}
                      >
                        {m.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button className="w-full border-t border-slate-100 py-3 text-center text-sm font-semibold text-blue-600 dark:border-white/[0.04] dark:text-blue-400">
          Show more team members (6) <ChevronDown className="ml-1 inline h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// --- Activity feed (SAMPLE) --------------------------------------------------

const ACT_META: Record<string, { icon: LucideIcon; tint: string }> = {
  metric: { icon: TrendingUp, tint: "emerald" },
  schedule: { icon: CalendarDays, tint: "blue" },
  blocked: { icon: TriangleAlert, tint: "amber" },
  done: { icon: CheckCircle2, tint: "emerald" },
  people: { icon: Users, tint: "violet" },
  report: { icon: FileText, tint: "blue" },
};

function ActivityFeed() {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-bold">
          Activity Feed
          <SampleTag />
        </h2>
        <button className="flex items-center gap-1 text-sm font-semibold text-blue-600 dark:text-blue-400">
          View all <ArrowRight className="h-4 w-4" />
        </button>
      </div>
      <div className={cn(CARD, "flex flex-col")}>
        <ul className="flex-1 divide-y divide-slate-100 dark:divide-white/[0.04]">
          {SAMPLE_ACTIVITY.map((a) => {
            const meta = ACT_META[a.kind];
            return (
              <li key={a.title} className="flex gap-3 px-4 py-3">
                <span className="w-14 shrink-0 pt-0.5 text-xs text-slate-400">{a.time}</span>
                <span
                  className={cn(
                    "grid h-7 w-7 shrink-0 place-items-center rounded-lg",
                    TINT[meta.tint],
                  )}
                >
                  <meta.icon className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold leading-snug">{a.title}</div>
                  <div className="mt-0.5 text-xs text-slate-400">{a.meta}</div>
                </div>
              </li>
            );
          })}
        </ul>
        <button className="m-3 flex items-center justify-center gap-2 rounded-xl bg-slate-50 py-2.5 text-sm font-semibold text-blue-600 transition hover:bg-slate-100 dark:bg-white/[0.04] dark:text-blue-300 dark:hover:bg-white/[0.07]">
          Go to Activity Center <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function SampleTag() {
  return (
    <span
      className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:bg-white/[0.06]"
      title="Placeholder — Team/Activity slices are not wired to live data yet"
    >
      Sample
    </span>
  );
}

// --- utils -------------------------------------------------------------------

function initials(source?: string | null): string {
  if (!source) return "•";
  const name = source.includes("@") ? source.split("@")[0] : source;
  const parts = name.split(/[.\s_-]+/).filter(Boolean);
  const two = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
  return (two || name.slice(0, 2)).toUpperCase();
}
