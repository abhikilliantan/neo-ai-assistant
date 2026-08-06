import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export interface QuickActionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  label: string;
}

/** Compact icon + label action. Hairline border, gradient-tinted hover glow. */
export const QuickActionButton = React.forwardRef<HTMLButtonElement, QuickActionButtonProps>(
  ({ icon: Icon, label, className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "group flex flex-col items-center justify-center gap-2 rounded-card border border-rd-border bg-rd-card p-4",
        "text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60",
        className,
      )}
      {...props}
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-control border border-rd-border bg-rd-panel text-rd-cyan transition-colors group-hover:bg-rd-grad group-hover:text-white">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <span className="text-xs font-medium">{label}</span>
    </button>
  ),
);
QuickActionButton.displayName = "QuickActionButton";
