import { AlertTriangle, Check, Zap } from "lucide-react";
import type { ToolInvocation } from "@neo/shared-types";
import { cn } from "@/lib/cn";

// A tool call is either a read-only LOOKUP or a side-effecting ACTION (a
// workflow — 7b/7d). The SSE "tool" frame carries only a NAME (arguments are
// withheld by design), so the frontend classifies by a known-name map. Only
// names explicitly marked `kind: "action"` render as actions; anything else —
// including a NEW workflow not yet listed here — falls through to the neutral
// generic chip. That is graceful: an unknown tool is under-labelled, but it is
// NEVER a crash and NEVER falsely presented as an action (mislabelling whether
// an action occurred is the worst outcome, so the fallback must stay neutral).
//
// Labels are past tense: the "tool" frame is emitted AFTER the tool ran, so
// nothing here is in-progress. Failure wording must make clear the action did
// NOT happen ("Couldn't create the task" ≠ "Created a task").
type ToolKind = "action" | "read";

const KNOWN_TOOLS: Record<string, { kind: ToolKind; ok: string; fail: string }> = {
  search_memory: {
    kind: "read",
    ok: "Searched your memories",
    fail: "Couldn't search your memories",
  },
  // Side-effecting workflow (7b). Add a workflow here to give it an action
  // label; until then it renders as the neutral generic chip below.
  create_task: {
    kind: "action",
    ok: "Created a task",
    fail: "Couldn't create the task",
  },
};

export function describeTool(name: string, ok: boolean): { kind: ToolKind; label: string } {
  const entry = KNOWN_TOOLS[name];
  if (!entry) {
    // Unknown/new tool → neutral generic chip. Never "action": we must not
    // assert an external action occurred when we cannot be sure it did.
    return { kind: "read", label: ok ? `Used ${name}` : `${name} failed` };
  }
  return { kind: entry.kind, label: ok ? entry.ok : entry.fail };
}

export function ToolChip({ invocation }: { invocation: ToolInvocation }) {
  const { name, ok } = invocation;
  const { kind, label } = describeTool(name, ok);
  const isAction = kind === "action";
  // Failure is failure (AlertTriangle) regardless of kind. On success, actions
  // use Zap so the action/lookup distinction survives without colour; reads
  // keep Check. Read-only chips are visually identical to before.
  const Icon = !ok ? AlertTriangle : isAction ? Zap : Check;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "text-[10px] uppercase tracking-wide",
        !ok
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
          : isAction
            ? "border-indigo-500/40 bg-indigo-500/10 text-indigo-700"
            : "bg-muted text-muted-foreground",
      )}
      aria-label={label}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}
