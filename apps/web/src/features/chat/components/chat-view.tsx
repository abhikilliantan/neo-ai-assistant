"use client";

import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useRef, useState } from "react";
import type { ApiErrorEnvelope, ChatMessage, ChatResponse } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { sendChat } from "@/services/chat";

export function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const mutation = useMutation({
    mutationFn: (m: ChatMessage[]) => sendChat(m),
    onSuccess: (r: ChatResponse) => setMessages((prev) => [...prev, r.message]),
    onError: (e) => setError(extractApiMessage(e) ?? "Something went wrong."),
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, mutation.isPending]);

  function onSend(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || mutation.isPending) return;
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setDraft("");
    mutation.mutate(next);
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
      <Card className="flex-1 overflow-hidden">
        <div ref={scrollRef} className="h-full overflow-auto p-4">
          {messages.length === 0 && !mutation.isPending ? (
            <p className="text-sm text-muted-foreground">
              Start a conversation. This is a mock backend — replies are canned.
            </p>
          ) : (
            <ul className="space-y-3">
              {messages.map((m, i) => (
                <MessageBubble key={i} role={m.role} content={m.content} />
              ))}
              {mutation.isPending && (
                <li className="flex justify-start">
                  <div className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                    Thinking…
                  </div>
                </li>
              )}
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
          disabled={mutation.isPending}
        />
        <Button type="submit" disabled={mutation.isPending || draft.trim() === ""}>
          Send
        </Button>
      </form>
    </div>
  );
}

function MessageBubble({ role, content }: { role: ChatMessage["role"]; content: string }) {
  const isUser = role === "user";
  return (
    <li className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {content}
      </div>
    </li>
  );
}

function extractApiMessage(err: unknown): string | null {
  if (!axios.isAxiosError(err)) return null;
  const body = err.response?.data as ApiErrorEnvelope | undefined;
  return body?.error?.message ?? null;
}
