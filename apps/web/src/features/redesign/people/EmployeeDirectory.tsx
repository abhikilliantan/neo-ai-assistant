"use client";

import { ChevronLeft, ChevronRight, Download, MoreHorizontal, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { AvatarStack, SampleTag, Sparkline } from "@/features/redesign/components";
import { DEPARTMENTS, DEPT_TAG, EMPLOYEES, type Dept, type Employee, type EmpStatus } from "./data";

export function EmployeeDirectory() {
  const [query, setQuery] = useState("");
  const [dept, setDept] = useState<"" | Dept>("");
  const [status, setStatus] = useState<"" | EmpStatus>("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return EMPLOYEES.filter(
      (e) =>
        (!q || e.name.toLowerCase().includes(q) || e.email.toLowerCase().includes(q)) &&
        (!dept || e.department === dept) &&
        (!status || e.status === status),
    );
  }, [query, dept, status]);

  return (
    <div className="glow-card p-0">
      {/* Header: title + search + filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rd-border px-5 py-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-rd-heading">Employee Directory (256)</h3>
          <SampleTag />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-rd-muted"
              aria-hidden
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search employees…"
              aria-label="Search employees"
              className="h-9 w-48 rounded-control border border-rd-border bg-rd-panel/50 pl-8 pr-3 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30"
            />
          </div>
          <Select
            value={dept}
            onChange={(v) => setDept(v as "" | Dept)}
            placeholder="All Departments"
            options={DEPARTMENTS}
          />
          <Select
            value={status}
            onChange={(v) => setStatus(v as "" | EmpStatus)}
            placeholder="Status"
            options={["Active", "On Leave"]}
          />
          <button
            type="button"
            aria-label="Export directory"
            className="flex h-9 w-9 items-center justify-center rounded-control border border-rd-border text-rd-muted hover:text-rd-heading"
          >
            <Download className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left">
          <thead>
            <tr className="border-b border-rd-border text-[11px] uppercase tracking-wide text-rd-muted">
              <Th className="pl-5">Employee</Th>
              <Th>Department</Th>
              <Th>Designation</Th>
              <Th>Location</Th>
              <Th>Status</Th>
              <Th>Performance</Th>
              <Th>Tenure</Th>
              <Th className="pr-5 text-right">Actions</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <Row key={e.email} e={e} />
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="py-10 text-center text-sm text-rd-muted">
            No employees match your filters.
          </p>
        )}
      </div>

      {/* Footer: pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rd-border px-5 py-3">
        <p className="text-xs text-rd-muted">Showing 1 to 10 of 256 results</p>
        <div className="flex items-center gap-1">
          <PageBtn label="Previous" icon={ChevronLeft} />
          <PageNum n={1} active />
          <PageNum n={2} />
          <PageNum n={3} />
          <span className="px-1 text-rd-muted">…</span>
          <PageNum n={26} />
          <PageBtn label="Next" icon={ChevronRight} />
        </div>
        <div className="flex items-center gap-2 text-xs text-rd-muted">
          Rows per page:
          <span className="rounded-control border border-rd-border px-2 py-1 text-rd-body">10</span>
        </div>
      </div>
    </div>
  );
}

function Row({ e }: { e: Employee }) {
  return (
    <tr className="border-b border-rd-border/60 last:border-b-0 hover:bg-rd-panel/40">
      <td className="py-3 pl-5 pr-3">
        <div className="flex items-center gap-3">
          <AvatarStack names={[e.name]} size={34} />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-rd-heading">{e.name}</p>
            <p className="truncate text-xs text-rd-muted">{e.email}</p>
          </div>
        </div>
      </td>
      <td className="px-3 py-3">
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[11px] font-medium",
            DEPT_TAG[e.department],
          )}
        >
          {e.department}
        </span>
      </td>
      <td className="px-3 py-3 text-sm text-rd-body">{e.designation}</td>
      <td className="px-3 py-3 text-sm text-rd-body">{e.location}</td>
      <td className="px-3 py-3">
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[11px] font-medium",
            e.status === "Active"
              ? "border-rd-green/40 bg-rd-green/10 text-rd-green"
              : "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
          )}
        >
          {e.status}
        </span>
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          <PerfRing pct={e.performance} />
          <Sparkline
            data={e.spark}
            color={e.performance >= 88 ? "green" : "amber"}
            height={24}
            className="w-16"
          />
        </div>
      </td>
      <td className="px-3 py-3 text-sm text-rd-body">{e.tenure}</td>
      <td className="py-3 pl-3 pr-5 text-right">
        <button
          type="button"
          aria-label={`Actions for ${e.name}`}
          className="inline-flex h-8 w-8 items-center justify-center rounded-control border border-rd-border text-rd-muted hover:text-rd-heading"
        >
          <MoreHorizontal className="h-4 w-4" aria-hidden />
        </button>
      </td>
    </tr>
  );
}

function PerfRing({ pct }: { pct: number }) {
  const color = pct >= 88 ? "hsl(var(--rd-green))" : "hsl(var(--rd-amber))";
  return (
    <div
      className="relative flex h-9 w-9 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${color} ${pct}%, hsl(var(--rd-panel)) 0)` }}
    >
      <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-rd-card text-[10px] font-semibold tabular-nums text-rd-heading">
        {pct}
      </span>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn("px-3 py-2.5 font-medium", className)}>{children}</th>;
}

function Select({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={placeholder}
      className="h-9 rounded-control border border-rd-border bg-rd-panel/50 px-2.5 text-sm text-rd-body focus:border-rd-border-hover focus:outline-none"
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function PageNum({ n, active }: { n: number; active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "flex h-8 min-w-8 items-center justify-center rounded-control px-2 text-sm transition-colors",
        active
          ? "bg-rd-grad text-white"
          : "border border-rd-border text-rd-body hover:text-rd-heading",
      )}
    >
      {n}
    </button>
  );
}

function PageBtn({ label, icon: Icon }: { label: string; icon: typeof ChevronLeft }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded-control border border-rd-border text-rd-muted hover:text-rd-heading"
    >
      <Icon className="h-4 w-4" aria-hidden />
    </button>
  );
}
