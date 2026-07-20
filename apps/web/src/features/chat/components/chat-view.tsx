"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Agent, ChatMessage, ToolInvocation } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { listAgents } from "@/services/agents";
import { streamChat } from "@/services/chat";
import { getConversation } from "@/services/conversations";
import { ConversationSidebar } from "@/features/chat/components/conversation-sidebar";
import { ToolChip } from "@/features/chat/components/tool-chip";

// Session-only extension of shared-types ChatMessage. Both `toolInvocations`
// (6e-1) and `agent` (6i-1) are LIVE UI state — populated from SSE frames
// during a stream and dropped on reload. They are NEVER sent back to
// /chat/stream (the request body still uses the plain {role, content}
// shape) and NEVER surface on history from /conversations/{id} — matches
// the ephemeral guarantees of both slices.
type UiMessage = ChatMessage & { toolInvocations?: ToolInvocation[]; agent?: string };

const DEFAULT_AGENT: Agent = {
  name: "assistant",
  description: "General-purpose Neo assistant.",
};

export function ChatView() {
  const queryClient = useQueryClient();

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Session-level agent selection (6i-2). NOT per-conversation — selection
  // is per-request until 6j adds persistence. Default matches the backend's
  // DEFAULT_AGENT_NAME so a fresh page load sends no `agent` key on the wire.
  const [selectedAgent, setSelectedAgent] = useState<string>(DEFAULT_AGENT.name);

  // The picker must NEVER break chat: if /agents fails or returns [],
  // we fall back to a single implicit "assistant" entry so the picker
  // still renders one option and streaming proceeds normally.
  const agentsQuery = useQuery({ queryKey: ["agents"], queryFn: listAgents });
  const agents: Agent[] = useMemo(() => {
    const list = agentsQuery.data;
    return list && list.length > 0 ? list : [DEFAULT_AGENT];
  }, [agentsQuery.data]);
  const selectedAgentMeta =
    agents.find((a) => a.name === selectedAgent) ?? agents[0] ?? DEFAULT_AGENT;

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
      // Omit `agent` on the default so the wire is byte-identical to pre-6h;
      // send the explicit name otherwise so the backend resolves it directly.
      agent: selectedAgent !== DEFAULT_AGENT.name ? selectedAgent : undefined,
      onMeta: ({ conversation_id, agent }) => {
        // First message in a brand-new conversation: adopt the server-assigned
        // id so subsequent sends thread into the same conversation.
        setActiveConversationId((prev) => prev ?? conversation_id);
        // Meta arrives BEFORE the first delta, so tagging the pending
        // assistant message here makes the label visible from stream start.
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { ...last, agent };
          }
          return next;
        });
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
                    agent={m.agent}
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

        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="agent-picker" className="text-xs text-muted-foreground">
            Agent
          </label>
          <select
            id="agent-picker"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            // Locked during streaming — switching mid-stream would make the
            // meta.agent label ambiguous about which agent produced the text
            // on screen. Also disabled while loading historical messages.
            disabled={streaming || loadingHistory}
            className={cn(
              "rounded-md border bg-background px-2 py-1 text-sm",
              "focus:outline-none focus:ring-2 focus:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {agents.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted-foreground">{selectedAgentMeta.description}</span>
        </div>

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

// Markdown element styling for assistant messages. No @tailwindcss/typography
// dependency — we style only what actually surfaces in chat, via a components
// map. Links open in a new tab with noopener + noreferrer (untrusted output).
// react-markdown is markdown-only by default (no rehype-raw, no
// allowDangerousHtml), so raw HTML in model output is escaped, not rendered.
const MARKDOWN_COMPONENTS: Components = {
  p: (props) => <p className="mb-2 last:mb-0" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  ul: (props) => <ul className="mb-2 list-disc pl-5 last:mb-0" {...props} />,
  ol: (props) => <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props} />,
  li: (props) => <li className="mb-0.5" {...props} />,
  h1: (props) => <h1 className="mb-2 mt-1 text-base font-semibold" {...props} />,
  h2: (props) => <h2 className="mb-2 mt-1 text-sm font-semibold" {...props} />,
  h3: (props) => <h3 className="mb-1 mt-1 text-sm font-semibold" {...props} />,
  blockquote: (props) => (
    <blockquote className="mb-2 border-l-2 border-muted-foreground/40 pl-3 italic" {...props} />
  ),
  a: ({ href, children, ...rest }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline underline-offset-2"
      {...rest}
    >
      {children}
    </a>
  ),
  // Inline vs. block code: react-markdown renders inline `code` bare and
  // fenced blocks as <pre><code>…</code></pre>. Style each layer where it
  // sits — `pre` gets the block chrome, `code` inside `pre` is transparent.
  code: (props) => (
    <code className="rounded bg-background/60 px-1 py-0.5 font-mono text-[0.85em]" {...props} />
  ),
  pre: (props) => (
    <pre
      className="mb-2 overflow-x-auto rounded-md bg-background/60 p-2 text-xs [&_code]:bg-transparent [&_code]:p-0"
      {...props}
    />
  ),
};

function MessageBubble({
  role,
  content,
  toolInvocations,
  agent,
  pending,
}: {
  role: ChatMessage["role"];
  content: string;
  toolInvocations?: ToolInvocation[];
  agent?: string;
  pending?: boolean;
}) {
  const isUser = role === "user";
  const chips = !isUser && toolInvocations && toolInvocations.length > 0;
  // Agent label is LIVE-only (set by meta frame during stream). Hidden for
  // the default agent — the picker already shows "assistant" and repeating
  // it on every bubble is noise. Non-default names ("recall", …) still show.
  const agentLabel = !isUser && agent && agent !== DEFAULT_AGENT.name;
  return (
    <li className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className="flex max-w-[75%] flex-col items-start gap-1">
        {agentLabel && (
          <span
            className="text-[10px] uppercase tracking-wide text-muted-foreground"
            aria-label={`Agent: ${agent}`}
          >
            {agent}
          </span>
        )}
        {chips && (
          <div className="flex flex-wrap gap-1" aria-label="Tools Neo used">
            {toolInvocations.map((t, i) => (
              <ToolChip key={i} invocation={t} />
            ))}
          </div>
        )}
        <div
          className={cn(
            "rounded-lg px-3 py-2 text-sm",
            // User text is literal — preserve whitespace, no markdown.
            isUser && "whitespace-pre-wrap bg-primary text-primary-foreground",
            !isUser && "bg-muted",
            pending && "text-muted-foreground",
          )}
        >
          {pending ? (
            "Thinking…"
          ) : isUser ? (
            content
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
              {content}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </li>
  );
}
