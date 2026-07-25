"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { ConversationSummary } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import {
  deleteConversation,
  listConversations,
  renameConversation,
} from "@/services/conversations";

type Props = {
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  // Called after a conversation is deleted so the thread view can clear itself
  // if the deleted one was active.
  onDeleted: (id: string) => void;
};

// Bucket a conversation by its most-recent activity into Today / Yesterday /
// Earlier. The list arrives already sorted newest-first, so preserving order
// while grouping keeps the buckets in the right sequence.
function dayBucket(iso: string): "Today" | "Yesterday" | "Earlier" {
  const d = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = d.getTime();
  if (t >= startOfToday) return "Today";
  if (t >= startOfToday - 86_400_000) return "Yesterday";
  return "Earlier";
}

function groupConversations(rows: ConversationSummary[]) {
  const order: Array<"Today" | "Yesterday" | "Earlier"> = ["Today", "Yesterday", "Earlier"];
  const groups = new Map<string, ConversationSummary[]>();
  for (const c of rows) {
    const key = dayBucket(c.last_message_at ?? c.created_at);
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(c);
  }
  return order.filter((k) => groups.has(k)).map((label) => ({ label, items: groups.get(label)! }));
}

export function ConversationSidebar({
  activeConversationId,
  onNewChat,
  onSelect,
  onDeleted,
}: Props) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  // Invalidating ["conversations"] refreshes BOTH the sidebar and the dashboard
  // count, which share this query key.
  const del = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: (_v, id) => {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      onDeleted(id);
    },
  });
  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });

  const groups = data ? groupConversations(data) : [];

  return (
    <aside className="glass flex h-full w-72 flex-col gap-3 rounded-card p-3 shadow-glow">
      <Button onClick={onNewChat} variant="gradient" className="w-full">
        <Plus className="h-4 w-4" />
        New chat
      </Button>

      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading && <p className="px-2 text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="px-2 text-sm text-danger">Failed to load.</p>}
        {data && data.length === 0 && (
          <p className="px-2 text-sm text-muted-foreground">No conversations yet.</p>
        )}
        {groups.map((group) => (
          <div key={group.label}>
            <p className="px-2 pb-1 pt-3 font-mono text-[10px] uppercase tracking-wider text-faint">
              {group.label}
            </p>
            <ul className="space-y-1">
              {group.items.map((c) => (
                <ConversationRow
                  key={c.id}
                  conversation={c}
                  active={c.id === activeConversationId}
                  onClick={() => onSelect(c.id)}
                  onRename={(title) => rename.mutate({ id: c.id, title })}
                  onDelete={() => del.mutate(c.id)}
                  deleting={del.isPending && del.variables === c.id}
                />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}

function ConversationRow({
  conversation,
  active,
  onClick,
  onRename,
  onDelete,
  deleting,
}: {
  conversation: ConversationSummary;
  active: boolean;
  onClick: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conversation.title ?? "");
  const stamp = conversation.last_message_at ?? conversation.created_at;

  function submitRename() {
    const t = draft.trim();
    if (t && t !== conversation.title) onRename(t);
    setEditing(false);
  }

  // Inline rename — replaces the row with an editable title field.
  if (editing) {
    return (
      <li>
        <div className="flex items-center gap-1 rounded-control px-1 py-1">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitRename();
              if (e.key === "Escape") setEditing(false);
            }}
            autoFocus
            aria-label="Conversation title"
            className="h-7 text-sm"
          />
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 shrink-0"
            onClick={submitRename}
            aria-label="Save title"
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 shrink-0"
            onClick={() => setEditing(false)}
            aria-label="Cancel rename"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "flex w-full flex-col gap-0.5 rounded-control px-3 py-2 text-left text-sm transition-colors",
          active
            ? "glass-hi border border-glass-border-strong text-foreground"
            : "text-muted-foreground hover:bg-glass hover:text-foreground",
        )}
      >
        {/* right padding leaves room for the hover/confirm actions */}
        <span className="truncate pr-16 font-medium">
          {conversation.title ?? "New conversation"}
        </span>
        <span className="text-xs text-faint">{formatRelative(stamp)}</span>
      </button>

      {confirming ? (
        <div className="absolute right-1 top-1.5 flex items-center gap-1 rounded-control glass-hi px-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-danger hover:bg-danger/15"
            onClick={onDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => setConfirming(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <div className="absolute right-1 top-1.5 hidden items-center gap-0.5 group-hover:flex">
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            onClick={() => {
              setDraft(conversation.title ?? "");
              setEditing(true);
            }}
            aria-label={`Rename ${conversation.title ?? "conversation"}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 hover:text-danger"
            onClick={() => setConfirming(true)}
            aria-label={`Delete ${conversation.title ?? "conversation"}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </li>
  );
}
