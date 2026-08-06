"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import type { ConversationSummary } from "@neo/shared-types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { listConversations } from "@/services/conversations";

type Bucket = "Today" | "Yesterday" | "Previous 7 Days" | "Older";

// Four buckets matching the mockup. List arrives newest-first, so grouping in
// place keeps each bucket ordered.
function dayBucket(iso: string): Bucket {
  const then = new Date(iso).getTime();
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (then >= startOfToday) return "Today";
  if (then >= startOfToday - 86_400_000) return "Yesterday";
  if (then >= startOfToday - 7 * 86_400_000) return "Previous 7 Days";
  return "Older";
}

function groupConversations(rows: ConversationSummary[]) {
  const order: Bucket[] = ["Today", "Yesterday", "Previous 7 Days", "Older"];
  const groups = new Map<Bucket, ConversationSummary[]>();
  for (const c of rows) {
    const key = dayBucket(c.last_message_at ?? c.created_at);
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(c);
  }
  return order.filter((k) => groups.has(k)).map((label) => ({ label, items: groups.get(label)! }));
}

export function ConversationsRail({
  activeConversationId,
  onNewChat,
  onSelect,
  className,
}: {
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });
  const groups = data ? groupConversations(data) : [];

  return (
    <aside className={cn("flex min-h-0 flex-col gap-3", className)}>
      <button
        type="button"
        onClick={onNewChat}
        className="flex w-full items-center justify-between rounded-xl border border-rd-cyan/40 bg-rd-cyan/10 px-4 py-3 text-sm font-medium text-rd-heading transition-colors hover:border-rd-cyan/70 hover:bg-rd-cyan/15"
      >
        <span className="inline-flex items-center gap-2">
          <Plus className="h-4 w-4 text-rd-cyan" aria-hidden />
          New Chat
        </span>
        <Plus className="h-4 w-4 text-rd-muted" aria-hidden />
      </button>

      <div className="glow-card flex min-h-0 flex-1 flex-col overflow-hidden p-0">
        <p className="border-b border-rd-border px-4 py-3 text-sm font-semibold text-rd-heading">
          Recent Conversations
        </p>
        <div className="min-h-0 flex-1 overflow-auto px-2 py-2">
          {isLoading && <p className="px-2 py-2 text-sm text-rd-muted">Loading…</p>}
          {isError && (
            <p className="px-2 py-2 text-sm text-rd-rose">Couldn’t load conversations.</p>
          )}
          {data && data.length === 0 && (
            <p className="px-2 py-2 text-sm text-rd-muted">No conversations yet.</p>
          )}
          {groups.map((group) => (
            <div key={group.label} className="mb-2">
              <p className="px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wider text-rd-muted">
                {group.label}
              </p>
              <ul className="space-y-1">
                {group.items.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(c.id)}
                      className={cn(
                        "group flex w-full items-center justify-between gap-2 rounded-control px-3 py-2 text-left transition-colors",
                        c.id === activeConversationId
                          ? "border border-rd-cyan/40 bg-rd-cyan/10"
                          : "border border-transparent hover:bg-rd-panel",
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-rd-heading">
                          {c.title ?? "New conversation"}
                        </span>
                        <span className="block text-xs text-rd-muted">
                          {formatRelative(c.last_message_at ?? c.created_at)}
                        </span>
                      </span>
                      <ChevronRight
                        className="h-4 w-4 shrink-0 text-rd-muted opacity-0 transition-opacity group-hover:opacity-100"
                        aria-hidden
                      />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {/* ponytail: no all-conversations route yet — the rail already lists
            every recent thread. Inert affordance until that page exists. */}
        <p className="border-t border-rd-border px-4 py-3 text-center text-sm font-medium text-rd-cyan">
          View All Conversations
        </p>
      </div>
    </aside>
  );
}
