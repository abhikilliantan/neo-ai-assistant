"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Cpu, HardDrive, PanelLeftClose, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { SampleTag } from "@/features/redesign/components";
import { NAV_GROUPS, navHref } from "./nav";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "sticky top-0 z-30 flex h-screen shrink-0 flex-col border-r border-rd-border bg-rd-panel",
        "transition-[width] duration-200 ease-out",
        collapsed ? "w-[68px]" : "w-64",
      )}
      aria-label="Primary navigation"
    >
      {/* Brand */}
      <div className="flex h-16 items-center gap-3 border-b border-rd-border px-4">
        <span
          className="gradient-ring relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rd-card text-sm font-bold tracking-tight text-rd-heading"
          aria-hidden
        >
          N
        </span>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold tracking-[0.18em] text-rd-heading">NEO</p>
            <p className="truncate text-[11px] text-rd-muted">AI Operating System</p>
          </div>
        )}
        {!collapsed && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Collapse sidebar"
            className="rounded-control p-1.5 text-rd-body transition-colors hover:bg-rd-card hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label ?? `group-${gi}`} className="space-y-1">
            {group.label && !collapsed && (
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-rd-muted">
                {group.label}
              </p>
            )}
            {group.items.map((item) => {
              const href = navHref(item.slug);
              const active = pathname === href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.slug}
                  href={href}
                  title={item.label}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-control px-2.5 py-2 text-sm transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60",
                    active
                      ? "bg-rd-card font-medium text-rd-heading"
                      : "text-rd-body hover:bg-rd-card/60 hover:text-rd-heading",
                    collapsed && "justify-center",
                  )}
                >
                  {active && (
                    <span
                      className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-rd-grad"
                      aria-hidden
                    />
                  )}
                  <Icon
                    className={cn("h-[18px] w-[18px] shrink-0", active && "text-rd-cyan")}
                    aria-hidden
                  />
                  {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                  {!collapsed && item.chevron && (
                    <ChevronRight className="h-4 w-4 shrink-0 text-rd-muted" aria-hidden />
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer widgets (sample data) */}
      <div className="space-y-3 border-t border-rd-border p-3">
        {!collapsed && (
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-rd-muted">
              System
            </span>
            <SampleTag />
          </div>
        )}
        <FooterMeter
          icon={Sparkles}
          label="System Health"
          value="Excellent · 98.6%"
          percent={98.6}
          color="green"
          collapsed={collapsed}
        />
        <FooterMeter
          icon={HardDrive}
          label="Memory Usage"
          value="6.2 / 16 GB"
          percent={38.75}
          color="cyan"
          collapsed={collapsed}
        />
        <div
          className={cn(
            "flex items-center gap-2 rounded-control border border-rd-border bg-rd-card px-2.5 py-2",
            collapsed && "justify-center",
          )}
          title="LLM Connected — GPT-4o Enterprise"
        >
          <Cpu className="h-4 w-4 shrink-0 text-rd-violet" aria-hidden />
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-rd-heading">GPT-4o Enterprise</p>
              <p className="truncate text-[10px] text-rd-muted">LLM Connected</p>
            </div>
          )}
          <span
            className="h-2 w-2 shrink-0 rounded-full bg-rd-green shadow-[0_0_8px_2px] shadow-rd-green/40"
            aria-hidden
          />
        </div>
      </div>
    </aside>
  );
}

function FooterMeter({
  icon: Icon,
  label,
  value,
  percent,
  color,
  collapsed,
}: {
  icon: typeof Cpu;
  label: string;
  value: string;
  percent: number;
  color: "green" | "cyan";
  collapsed: boolean;
}) {
  const pct = Math.max(0, Math.min(100, percent));
  if (collapsed) {
    return (
      <div className="flex justify-center" title={`${label} — ${value}`}>
        <Icon className={cn("h-4 w-4", color === "green" ? "text-rd-green" : "text-rd-cyan")} />
      </div>
    );
  }
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[11px] text-rd-body">
          <Icon className="h-3.5 w-3.5" aria-hidden />
          {label}
        </span>
        <span className="text-[11px] tabular-nums text-rd-muted">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-rd-card">
        <div
          className={cn("h-full rounded-full", color === "green" ? "bg-rd-green" : "bg-rd-grad")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
