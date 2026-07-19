"use client";

import { useQuery } from "@tanstack/react-query";
import type { ConversationSummary } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { listConversations } from "@/services/conversations";

type Props = {
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelect: (id: string) => void;
};

export function ConversationSidebar({ activeConversationId, onNewChat, onSelect }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  return (
    <aside className="flex h-full w-72 flex-col gap-3 border-r pr-4">
      <Button onClick={onNewChat} variant="outline" className="w-full">
        + New chat
      </Button>

      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-red-500">Failed to load.</p>}
        {data && data.length === 0 && (
          <p className="text-sm text-muted-foreground">No conversations yet.</p>
        )}
        {data && data.length > 0 && (
          <ul className="space-y-1">
            {data.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                active={c.id === activeConversationId}
                onClick={() => onSelect(c.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function ConversationRow({
  conversation,
  active,
  onClick,
}: {
  conversation: ConversationSummary;
  active: boolean;
  onClick: () => void;
}) {
  const stamp = conversation.last_message_at ?? conversation.created_at;
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left text-sm transition-colors",
          "hover:bg-muted",
          active && "bg-muted",
        )}
      >
        <span className="truncate font-medium">{conversation.title ?? "New conversation"}</span>
        <span className="text-xs text-muted-foreground">{formatRelative(stamp)}</span>
      </button>
    </li>
  );
}
