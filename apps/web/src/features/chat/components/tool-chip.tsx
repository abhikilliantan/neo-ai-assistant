import { AlertTriangle, Check } from "lucide-react";
import type { ToolInvocation } from "@neo/shared-types";
import { cn } from "@/lib/cn";

// Human label per tool. Add cases as new tools land; the fallback keeps
// unknown tools legible without a code change. ok=false phrasings are past
// tense — the 6e-1 "tool" frame is emitted AFTER the tool ran, so nothing
// on this chip is in-progress.
export function labelForTool(name: string, ok: boolean): string {
  switch (name) {
    case "search_memory":
      return ok ? "Searched your memories" : "Couldn't search your memories";
    default:
      return ok ? `Used ${name}` : `${name} failed`;
  }
}

export function ToolChip({ invocation }: { invocation: ToolInvocation }) {
  const { name, ok } = invocation;
  const label = labelForTool(name, ok);
  const Icon = ok ? Check : AlertTriangle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "text-[10px] uppercase tracking-wide text-muted-foreground",
        ok ? "bg-muted" : "border-amber-500/40 bg-amber-500/10 text-amber-700",
      )}
      aria-label={label}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}
