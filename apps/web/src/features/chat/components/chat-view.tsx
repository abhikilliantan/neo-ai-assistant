"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { streamChat } from "@/services/chat";

export function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Cancel any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  function onSend(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || streaming) return;
    setError(null);
    setDraft("");

    const history: ChatMessage[] = [...messages, { role: "user", content: text }];
    // Optimistic: append user + empty assistant placeholder. Deltas append into
    // the last message; onDone finalizes; onError drops the placeholder.
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    void streamChat(history, {
      signal: controller.signal,
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
      },
      onError: (err) => {
        setError(err.message || "Something went wrong.");
        // Drop the empty/partial assistant bubble.
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          return last?.role === "assistant" ? prev.slice(0, -1) : prev;
        });
        setStreaming(false);
        abortRef.current = null;
      },
    });
  }

  const showEmptyState = messages.length === 0 && !streaming;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
      <Card className="flex-1 overflow-hidden">
        <div ref={scrollRef} className="h-full overflow-auto p-4">
          {showEmptyState ? (
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
          disabled={streaming}
        />
        <Button type="submit" disabled={streaming || draft.trim() === ""}>
          Send
        </Button>
      </form>
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
