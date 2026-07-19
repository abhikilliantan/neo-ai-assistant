"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { streamChat } from "@/services/chat";
import { getConversation } from "@/services/conversations";
import { ConversationSidebar } from "@/features/chat/components/conversation-sidebar";

export function ChatView() {
  const queryClient = useQueryClient();

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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

    const history: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    void streamChat(history, {
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
  pending,
}: {
  role: ChatMessage["role"];
  content: string;
  pending?: boolean;
}) {
  const isUser = role === "user";
  return (
    <li className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
          pending && "text-muted-foreground",
        )}
      >
        {pending ? "Thinking…" : content}
      </div>
    </li>
  );
}
