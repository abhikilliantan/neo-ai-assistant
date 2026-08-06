import { notFound } from "next/navigation";
import {
  Activity,
  Bot,
  Cpu,
  FileText,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  TrendingUp,
  Upload,
  Users,
} from "lucide-react";
import {
  AgentCard,
  AlertRow,
  CompanyStatusCard,
  GlowCard,
  MetricCard,
  ProjectCard,
  QuickActionButton,
  RingGauge,
  SampleTag,
  SectionHeader,
  Sparkline,
  StatTile,
} from "@/features/redesign/components";

// Internal Phase-0 preview: hidden (404) in production builds so it can't ship.
export const metadata = { title: "Design System — Internal Preview" };

const spark = [12, 18, 14, 22, 19, 28, 24, 33, 30, 41, 38, 46];
const spark2 = [40, 38, 42, 36, 34, 30, 33, 28, 26, 24, 27, 22];

export default function DesignSystemPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="min-h-screen bg-rd-base px-6 py-8 text-rd-body sm:px-10">
      <div className="mx-auto max-w-6xl space-y-12">
        {/* Header / guard banner */}
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-rd-heading">
              Neo Design System
            </h1>
            <p className="mt-1 text-sm text-rd-body">
              Phase 0 — primitive kit on the dark AI-OS theme. Temporary review page.
            </p>
          </div>
          <span className="rounded-full border border-rd-amber/40 bg-rd-amber/10 px-3 py-1 text-xs font-medium text-rd-amber">
            Internal · dev-only
          </span>
        </header>

        {/* Stat tiles */}
        <section>
          <SectionHeader title="Stat tiles" subtitle="Icon · label · value · delta" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile icon={Users} label="Active users" value={12840} delta={4.2} />
            <StatTile icon={Cpu} label="Compute load" value="63%" delta={-1.8} />
            <StatTile icon={Activity} label="Requests / min" value={9412} delta={12.5} />
            <StatTile icon={Bot} label="Agents online" value={18} delta={0} />
          </div>
        </section>

        {/* Metric cards */}
        <section>
          <SectionHeader
            title="Metric cards"
            subtitle="Value + delta over a colored sparkline"
            action={<SampleTag />}
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <MetricCard label="Revenue" value="$1.2M" delta={8.4} trend={spark} color="cyan" />
            <MetricCard label="Churn" value="2.3%" delta={-0.6} trend={spark2} color="rose" />
            <MetricCard label="Pipeline" value={342} delta={5.1} trend={spark} color="violet" />
          </div>
        </section>

        {/* Ring gauges + sparklines */}
        <section>
          <SectionHeader title="Ring gauge & sparkline" subtitle="Recharts, gradient stroke" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <GlowCard sample className="flex items-center justify-around">
              <RingGauge value={78} label="healthy" />
              <RingGauge value={46} size={110} label="load" />
            </GlowCard>
            <GlowCard sample className="space-y-4">
              <div>
                <p className="mb-1 text-sm text-rd-body">Cyan trend</p>
                <Sparkline data={spark} color="cyan" />
              </div>
              <div>
                <p className="mb-1 text-sm text-rd-body">Green trend</p>
                <Sparkline data={spark} color="green" />
              </div>
              <div>
                <p className="mb-1 text-sm text-rd-body">Amber trend</p>
                <Sparkline data={spark2} color="amber" />
              </div>
            </GlowCard>
          </div>
        </section>

        {/* Company status */}
        <section>
          <SectionHeader title="Company status cards" subtitle="Ring % · revenue · trend" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <CompanyStatusCard
              name="Aurora Robotics"
              percent={82}
              revenue={1_240_000}
              delta={6.2}
              trend={spark}
              color="cyan"
              sample
            />
            <CompanyStatusCard
              name="Nimbus Health"
              percent={54}
              revenue={512_000}
              delta={-2.1}
              trend={spark2}
              color="rose"
              sample
            />
          </div>
        </section>

        {/* Agents */}
        <section>
          <SectionHeader title="Agent cards" subtitle="Name · role · load · status" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <AgentCard name="Atlas" role="Project Analyst" percent={72} status="active" />
            <AgentCard name="Vega" role="Research Scout" percent={34} status="idle" />
            <AgentCard name="Orion" role="Data Broker" percent={0} status="offline" />
          </div>
        </section>

        {/* Projects */}
        <section>
          <SectionHeader title="Project cards" subtitle="Status · progress · risk · AI forecast" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <ProjectCard
              name="Falcon Migration"
              status="on-track"
              progress={68}
              owner="A. Khan"
              risk="low"
              prediction="On pace to finish 3 days early based on current velocity."
            />
            <ProjectCard
              name="Ledger Rewrite"
              status="at-risk"
              progress={41}
              owner="M. Osei"
              risk="medium"
              prediction="Two blockers likely to slip the QA milestone by ~1 week."
            />
          </div>
        </section>

        {/* Alerts */}
        <section>
          <SectionHeader title="Alert rows" subtitle="Severity pill · title · meta" />
          <GlowCard sample>
            <AlertRow
              severity="HIGH"
              title="Payment webhook failing — 5xx from provider"
              meta="2m ago"
            />
            <AlertRow severity="MEDIUM" title="Latency spike on /service/ask" meta="14m ago" />
            <AlertRow severity="LOW" title="Nightly backup completed with warnings" meta="1h ago" />
          </GlowCard>
        </section>

        {/* Quick actions */}
        <section>
          <SectionHeader title="Quick actions" subtitle="Icon + label" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <QuickActionButton icon={Plus} label="New project" />
            <QuickActionButton icon={MessageSquarePlus} label="Ask Neo" />
            <QuickActionButton icon={Upload} label="Upload" />
            <QuickActionButton icon={FileText} label="Report" />
            <QuickActionButton icon={TrendingUp} label="Forecast" />
            <QuickActionButton icon={RefreshCw} label="Sync" />
          </div>
        </section>
      </div>
    </main>
  );
}
