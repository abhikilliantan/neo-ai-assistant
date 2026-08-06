import { cn } from "@/lib/cn";

export interface SampleTagProps {
  /** "inline" sits next to a title (default); "corner" floats top-right of a
   *  positioned parent (used by GlowCard's `sample` overlay). */
  variant?: "inline" | "corner";
  className?: string;
}

/** Subtle "sample" chip for any widget not yet backed by real data. */
export function SampleTag({ variant = "inline", className }: SampleTagProps) {
  return (
    <span
      className={cn(
        "inline-flex select-none items-center rounded-full border border-rd-border bg-rd-panel",
        "px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rd-muted",
        variant === "corner" && "absolute right-3 top-3",
        className,
      )}
    >
      sample
    </span>
  );
}
