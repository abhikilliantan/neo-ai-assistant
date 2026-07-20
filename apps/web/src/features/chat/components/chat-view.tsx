"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, ToolInvocation } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { streamChat } from "@/services/chat";
import { getConversation } from "@/services/conversations";
import { ConversationSidebar } from "@/features/chat/components/conversation-sidebar";
import { ToolChip } from "@/features/chat/components/tool-chip";

// Session-only extension of shared-types ChatMessage. `toolInvocations` is
// LIVE UI state — populated from SSE "tool" frames during a stream and
// dropped on reload. It is NEVER sent back to /chat/stream (the request
// body still uses the plain {role, content} shape) and NEVER surfaces on
// history from /conversations/{id} — that's correct and matches 6e-1's
// ephemeral guarantee.
type UiMessage = ChatMessage & { toolInvocations?: ToolInvocation[] };

export function ChatView() {
  const queryClient = useQueryClient();

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const startNewChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    setStreaming(false);
  }, []);

  const loadConversation = useCallback(
    async (id: string) => {
      if (id === activeConversationId || streaming) {
        // ponytail: no-op if already active; disallow switching mid-stream
        // to avoid a lost-write on Txn B against the wrong conversation.
        if (id === activeConversationId) return;
      }
      abortRef.current?.abort();
      abortRef.current = null;
      setError(null);
      setLoadingHistory(true);
      try {
        const detail = await getConversation(id);
        setActiveConversationId(detail.id);
        setMessages(detail.messages.map((m) => ({ role: m.role, content: m.content })));
      } catch (e) {
        setError((e as Error).message || "Could not load conversation.");
      } finally {
        setLoadingHistory(false);
      }
    },
    [activeConversationId, streaming],
  );

  function onSend(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || streaming) return;
    setError(null);
    setDraft("");

    // Request body is the plain shared-types shape — toolInvocations is
    // frontend-only state and MUST NOT be sent back to the backend.
    const requestHistory: ChatMessage[] = messages
      .map(({ role, content }) => ({ role, content }))
      .concat({ role: "user", content: text });
    setMessages([...messages, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    void streamChat(requestHistory, {
      signal: controller.signal,
      conversationId: activeConversationId ?? undefined,
      onMeta: (cid) => {
        // First message in a brand-new conversation: adopt the server-assigned id
        // so subsequent sends thread into the same conversation.
        setActiveConversationId((prev) => prev ?? cid);
      },
      onDelta: (chunk) =>
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { ...last, content: last.content + chunk };
          }
          return next;
        }),
      onTool: ({ tool_name, tool_ok }) =>
        setMessages((prev) => {
          // Same immutable-update pattern as onDelta — append the invocation
          // to the CURRENT in-flight assistant message's toolInvocations.
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = {
              ...last,
              toolInvocations: [...(last.toolInvocations ?? []), { name: tool_name, ok: tool_ok }],
            };
          }
          return next;
        }),
      onDone: () => {
        setStreaming(false);
        abortRef.current = null;
        // Refresh sidebar so a new conversation appears / title fills in / row bumps to top.
        void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      },
      onError: (err) => {
        setError(err.message || "Something went wrong.");
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          return last?.role === "assistant" ? prev.slice(0, -1) : prev;
        });
        setStreaming(false);
        abortRef.current = null;
      },
    });
  }

  const showEmptyState = messages.length === 0 && !streaming && !loadingHistory;

  return (
    <div className="flex h-full gap-4">
      <ConversationSidebar
        activeConversationId={activeConversationId}
        onNewChat={startNewChat}
        onSelect={(id) => void loadConversation(id)}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <Card className="flex-1 overflow-hidden">
          <div ref={scrollRef} className="h-full overflow-auto p-4">
            {loadingHistory ? (
              <p className="text-sm text-muted-foreground">Loading conversation…</p>
            ) : showEmptyState ? (
              <p className="text-sm text-muted-foreground">Start a conversation.</p>
            ) : (
              <ul className="space-y-3">
                {messages.map((m, i) => (
                  <MessageBubble
                    key={i}
                    role={m.role}
                    content={m.content}
                    toolInvocations={m.toolInvocations}
                    pending={
                      streaming &&
                      i === messages.length - 1 &&
                      m.role === "assistant" &&
                      m.content === ""
                    }
                  />
                ))}
              </ul>
            )}
          </div>
        </Card>

        {error && (
          <p role="alert" className="text-sm text-red-500">
            {error}
          </p>
        )}

        <form className="flex gap-2" onSubmit={onSend}>
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask anything…"
            aria-label="Message"
            disabled={streaming || loadingHistory}
          />
          <Button type="submit" disabled={streaming || loadingHistory || draft.trim() === ""}>
            Send
          </Button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({
  role,
  content,
  toolInvocations,
  pending,
}: {
  role: ChatMessage["role"];
  content: string;
  toolInvocations?: ToolInvocation[];
  pending?: boolean;
}) {
  const isUser = role === "user";
  const chips = !isUser && toolInvocations && toolInvocations.length > 0;
  return (
    <li className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className="flex max-w-[75%] flex-col items-start gap-1">
        {chips && (
          <div className="flex flex-wrap gap-1" aria-label="Tools Neo used">
            {toolInvocations.map((t, i) => (
              <ToolChip key={i} invocation={t} />
            ))}
          </div>
        )}
        <div
          className={cn(
            "whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted",
            pending && "text-muted-foreground",
          )}
        >
          {pending ? "Thinking…" : content}
        </div>
      </div>
    </li>
  );
}
