import { AlertTriangle, Check, Zap } from "lucide-react";
import type { ToolInvocation } from "@neo/shared-types";
import { cn } from "@/lib/cn";

// A tool call is either a read-only LOOKUP or a side-effecting ACTION (a
// workflow — 7b/7d). The SSE "tool" frame carries only a NAME (arguments are
// withheld by design), so the frontend classifies by a known-name map. Only
// names explicitly marked `kind: "action"` render as actions; anything else —
// including a NEW workflow not yet listed here — falls through to the neutral
// generic chip. Mislabelling whether an action occurred is the worst outcome,
// so the fallback stays neutral. Labels are past tense: the "tool" frame is
// emitted AFTER the tool ran.
type ToolKind = "action" | "read";

const KNOWN_TOOLS: Record<string, { kind: ToolKind; ok: string; fail: string }> = {
  search_memory: {
    kind: "read",
    ok: "Searched your memories",
    fail: "Couldn't search your memories",
  },
  search_documents: {
    kind: "read",
    ok: "Searched your documents",
    fail: "Couldn't search your documents",
  },
  create_task: {
    kind: "action",
    ok: "Created a task",
    fail: "Couldn't create the task",
  },
};

// Placeholder/dev tools never shown in production — "echo" is the scaffold tool.
const HIDDEN_TOOLS = new Set(["echo"]);

export function describeTool(name: string, ok: boolean): { kind: ToolKind; label: string } {
  const entry = KNOWN_TOOLS[name];
  if (!entry) {
    // Unknown/new tool → neutral generic chip. Never "action": we must not
    // assert an external action occurred when we cannot be sure it did.
    return { kind: "read", label: ok ? `Used ${name}` : `${name} failed` };
  }
  return { kind: entry.kind, label: ok ? entry.ok : entry.fail };
}

/**
 * ONE honest chip per tool per message. Hides placeholder tools (echo), drops
 * duplicates, and resolves a same-tool contradiction (e.g. a memory search that
 * ran twice, once failing) to a SINGLE truthful state — the last outcome — so
 * the UI never shows two contradictory memory chips.
 */
export function consolidateInvocations(invocations: ToolInvocation[]): ToolInvocation[] {
  const byName = new Map<string, ToolInvocation>();
  for (const inv of invocations) {
    if (HIDDEN_TOOLS.has(inv.name)) continue;
    byName.set(inv.name, inv); // last write wins → the final state for that tool
  }
  return [...byName.values()];
}

export function ToolChip({ invocation }: { invocation: ToolInvocation }) {
  const { name, ok } = invocation;
  const { kind, label } = describeTool(name, ok);
  const isAction = kind === "action";
  // One honest visual state: WARN on failure; INFO (accent) for a successful
  // action; OK (success) for a successful read. Icon reinforces state without
  // relying on colour alone.
  const Icon = !ok ? AlertTriangle : isAction ? Zap : Check;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "font-mono text-[10px] uppercase tracking-wide",
        !ok
          ? "border-warn/40 bg-warn/15 text-warn"
          : isAction
            ? "border-accent/40 bg-accent/15 text-accent"
            : "border-success/40 bg-success/15 text-success",
      )}
      aria-label={label}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}
