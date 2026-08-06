import { cn } from "@/lib/cn";

export type Severity = "HIGH" | "MEDIUM" | "LOW";

const PILL: Record<Severity, string> = {
  HIGH: "border-rd-rose/40 bg-rd-rose/10 text-rd-rose",
  MEDIUM: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  LOW: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
};

export interface AlertRowProps {
  severity: Severity;
  title: string;
  meta?: string;
  className?: string;
}

/** One alert line: severity pill + title + optional meta (source, time). */
export function AlertRow({ severity, title, meta, className }: AlertRowProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-rd-border py-2.5 last:border-b-0",
        className,
      )}
    >
      <span
        className={cn(
          "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide",
          PILL[severity],
        )}
      >
        {severity}
      </span>
      <span className="flex-1 truncate text-sm text-rd-heading">{title}</span>
      {meta && <span className="shrink-0 text-xs text-rd-muted">{meta}</span>}
    </div>
  );
}
