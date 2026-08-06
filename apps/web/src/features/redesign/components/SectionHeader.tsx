import * as React from "react";
import { cn } from "@/lib/cn";

export interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  /** Optional right-aligned slot (actions, filters, a SampleTag…). */
  action?: React.ReactNode;
  className?: string;
}

/** Section title + optional subtitle, with a gradient accent bar. */
export function SectionHeader({ title, subtitle, action, className }: SectionHeaderProps) {
  return (
    <div className={cn("mb-4 flex items-end justify-between gap-4", className)}>
      <div className="flex items-center gap-3">
        <span className="h-6 w-1 rounded-full bg-rd-grad" aria-hidden />
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-rd-heading">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-rd-body">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}
