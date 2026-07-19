"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import type { ChatMessage } from "@/features/chat/types";

export function ChatView() {
  const [messages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");

  // ponytail: UI only. Wire to /api/chat once the AI engine ships.
  const onSend = () => {
    if (!draft.trim()) return;
    setDraft("");
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
      <Card className="flex-1 overflow-auto p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Start a conversation…</p>
        ) : (
          <ul className="space-y-3">
            {messages.map((m) => (
              <li key={m.id} className="text-sm">
                <span className="font-medium">{m.role}: </span>
                {m.content}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask anything…"
          aria-label="Message"
        />
        <Button type="submit">Send</Button>
      </form>
    </div>
  );
}
