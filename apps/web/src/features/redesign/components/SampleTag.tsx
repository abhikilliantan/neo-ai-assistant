import { cn } from "@/lib/cn";

/** Subtle "sample" chip for any widget not yet backed by real data. */
export function SampleTag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex select-none items-center rounded-full border border-rd-border bg-rd-panel/70",
        "px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rd-muted",
        className,
      )}
    >
      sample
    </span>
  );
}
