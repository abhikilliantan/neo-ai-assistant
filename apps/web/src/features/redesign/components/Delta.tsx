import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatDelta } from "./format";

/** Signed change indicator: green up, rose down, muted flat. Shared by tiles. */
export function Delta({
  value,
  suffix = "%",
  className,
}: {
  value: number;
  suffix?: string;
  className?: string;
}) {
  const dir = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const Icon = dir === "up" ? ArrowUpRight : dir === "down" ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        dir === "up" && "text-rd-green",
        dir === "down" && "text-rd-rose",
        dir === "flat" && "text-rd-muted",
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {formatDelta(value)}
      {suffix}
    </span>
  );
}
