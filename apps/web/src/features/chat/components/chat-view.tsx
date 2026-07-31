"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Mic, Paperclip, Send, Sparkles, User } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Agent, ChatMessage, ToolInvocation } from "@neo/shared-types";
import { MobileDrawer } from "@/components/layout/mobile-drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { useUiStore } from "@/store/ui";
import { listAgents } from "@/services/agents";
// TODO: restore streaming once streaming+tools is wired. `streamChat` is kept
// in services/chat.ts and returns here then; the chat UI routes through the
// non-streaming sendChat for now because that's the path the tool loop
// (query_dataset / list_datasets) runs on.
import { sendChat } from "@/services/chat";
import { getConversation } from "@/services/conversations";
import { ConversationSidebar } from "@/features/chat/components/conversation-sidebar";
import { ToolChip, consolidateInvocations } from "@/features/chat/components/tool-chip";

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

  // Mobile-only (< md) conversation-history drawer. On md+ the fixed w-72 rail
  // stays and these are unused.
  const conversationDrawerOpen = useUiStore((s) => s.conversationDrawerOpen);
  const openConversationDrawer = useUiStore((s) => s.openConversationDrawer);
  const closeConversationDrawer = useUiStore((s) => s.closeConversationDrawer);

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

    // Non-streaming path: the tool loop runs server-side and we get the final
    // message back in one response (content + tool_invocations + agent). The
    // pending assistant bubble shows "Thinking…" until it resolves.
    void (async () => {
      try {
        const res = await sendChat(requestHistory, {
          signal: controller.signal,
          conversationId: activeConversationId ?? undefined,
          // Omit `agent` on the default so the wire is byte-identical to pre-6h;
          // send the explicit name otherwise so the backend resolves it directly.
          agent: selectedAgent !== DEFAULT_AGENT.name ? selectedAgent : undefined,
        });
        // First message in a brand-new conversation: adopt the server-assigned
        // id so subsequent sends thread into the same conversation.
        setActiveConversationId((prev) => prev ?? res.conversation_id);
        // Replace the pending assistant bubble with the final answer, carrying
        // the tool invocations + resolved agent for the chip / label.
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = {
              role: "assistant",
              content: res.message.content,
              toolInvocations: res.tool_invocations,
              agent: res.agent,
            };
          }
          return next;
        });
        setStreaming(false);
        abortRef.current = null;
        // Refresh sidebar so a new conversation appears / title fills in / row bumps to top.
        void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      } catch (e) {
        // Aborted (unmount / new chat / conversation switch): drop silently, but
        // still remove the empty pending assistant bubble so it can't linger in
        // the list and get re-sent as empty history on the next turn.
        if (controller.signal.aborted) {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            return last?.role === "assistant" && last.content === "" ? prev.slice(0, -1) : prev;
          });
          return;
        }
        setError((e as Error).message || "Something went wrong.");
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          return last?.role === "assistant" ? prev.slice(0, -1) : prev;
        });
        setStreaming(false);
        abortRef.current = null;
      }
    })();
  }

  const showEmptyState = messages.length === 0 && !streaming && !loadingHistory;

  return (
    // fixed-sidebar layout (from the earlier layout fix): min-h-0 chain keeps ONLY
    // the message thread scrolling; the composer stays pinned.
    <div className="flex h-full gap-4">
      <ConversationSidebar
        activeConversationId={activeConversationId}
        onNewChat={startNewChat}
        onSelect={(id) => void loadConversation(id)}
        onDeleted={(id) => {
          // Deleting the active thread clears the view back to the empty state.
          if (id === activeConversationId) startNewChat();
        }}
      />

      {/* Mobile-only: the same conversation list inside a slide-over drawer.
          Selecting a thread or starting a new chat closes the drawer. */}
      <MobileDrawer
        open={conversationDrawerOpen}
        onClose={closeConversationDrawer}
        label="Conversations"
        side="left"
      >
        <ConversationSidebar
          className="flex h-full w-full flex-col gap-3 p-3"
          activeConversationId={activeConversationId}
          onNewChat={() => {
            startNewChat();
            closeConversationDrawer();
          }}
          onSelect={(id) => {
            void loadConversation(id);
            closeConversationDrawer();
          }}
          onDeleted={(id) => {
            if (id === activeConversationId) startNewChat();
          }}
        />
      </MobileDrawer>

      <div className="flex min-w-0 flex-1 flex-col gap-4">
        {/* Mobile-only entry point to past conversations — the w-72 rail is
            hidden < md, so this opens the same list in a slide-over drawer. */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={openConversationDrawer}
          aria-label="Show conversation history"
          className="h-11 w-fit gap-2 md:hidden"
        >
          <History className="h-4 w-4" />
          Conversations
        </Button>

        <div className="glass min-h-0 flex-1 overflow-hidden rounded-card shadow-glow">
          <div ref={scrollRef} className="h-full overflow-auto p-4 md:p-6">
            {loadingHistory ? (
              <p className="text-sm text-muted-foreground">Loading conversation…</p>
            ) : showEmptyState ? (
              <EmptyState />
            ) : (
              <ul className="mx-auto flex max-w-3xl flex-col gap-5">
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
        </div>

        {/* One honest status area for the whole composer. */}
        {error ? (
          <p
            role="alert"
            className="inline-flex w-fit items-center gap-1.5 rounded-control border border-danger/40 bg-danger/15 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-danger"
          >
            {error}
          </p>
        ) : streaming ? (
          <p className="inline-flex w-fit items-center gap-2 rounded-control border border-accent/40 bg-accent/15 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden />
            Neo is responding
          </p>
        ) : null}

        <div className="glass-2 rounded-card p-3 shadow-glow">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <label
              htmlFor="agent-picker"
              className="font-mono text-[10px] uppercase tracking-wide text-faint"
            >
              Agent
            </label>
            <select
              id="agent-picker"
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              // Locked during streaming — switching mid-stream would make the
              // meta.agent label ambiguous about which agent produced the text.
              disabled={streaming || loadingHistory}
              className={cn(
                "max-w-full min-w-0 rounded-control border border-input bg-glass px-2 py-1 text-sm text-foreground",
                "focus:outline-none focus:ring-2 focus:ring-accent/40",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              {agents.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))}
            </select>
            <span className="w-full text-xs text-muted-foreground sm:w-auto sm:flex-1 sm:truncate">
              {selectedAgentMeta.description}
            </span>
          </div>

          {/* Composer controls are 44px (h-11/w-11) on mobile for comfortable
              touch targets, reverting to the desktop 40px (h-10) at md+. */}
          <form className="flex items-center gap-2" onSubmit={onSend}>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled
              title="Attachments (coming soon)"
              aria-label="Attach a file (coming soon)"
              className="h-11 w-11 shrink-0 md:h-10 md:w-10"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask anything…"
              aria-label="Message"
              disabled={streaming || loadingHistory}
              className="h-11 min-w-0 flex-1 md:h-10"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled
              title="Voice input (coming soon)"
              aria-label="Voice input (coming soon)"
              className="h-11 w-11 shrink-0 md:h-10 md:w-10"
            >
              <Mic className="h-4 w-4" />
            </Button>
            <Button
              type="submit"
              variant="gradient"
              size="icon"
              disabled={streaming || loadingHistory || draft.trim() === ""}
              aria-label="Send message"
              className="h-11 w-11 shrink-0 md:h-10 md:w-10"
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-card bg-accent-grad shadow-glow">
        <Sparkles className="h-6 w-6 text-on-accent" aria-hidden />
      </span>
      <p className="text-sm font-medium text-foreground">Start a conversation</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        Ask about your documents, your saved context, or anything else. Neo answers from what it can
        actually find.
      </p>
    </div>
  );
}

// Markdown element styling for assistant messages. No @tailwindcss/typography
// dependency — we style only what actually surfaces in chat, via a components
// map. Links open in a new tab with noopener + noreferrer (untrusted output).
// react-markdown is markdown-only by default (no rehype-raw, no
// allowDangerousHtml), so raw HTML in model output is escaped, not rendered.
const MARKDOWN_COMPONENTS: Components = {
  p: (props) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
  strong: (props) => <strong className="font-semibold text-foreground" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  ul: (props) => <ul className="mb-2 list-disc pl-5 last:mb-0" {...props} />,
  ol: (props) => <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props} />,
  li: (props) => <li className="mb-0.5" {...props} />,
  h1: (props) => <h1 className="mb-2 mt-1 text-base font-semibold text-foreground" {...props} />,
  h2: (props) => <h2 className="mb-2 mt-1 text-sm font-semibold text-foreground" {...props} />,
  h3: (props) => <h3 className="mb-1 mt-1 text-sm font-semibold text-foreground" {...props} />,
  blockquote: (props) => (
    <blockquote
      className="mb-2 border-l-2 border-accent/40 pl-3 italic text-muted-foreground"
      {...props}
    />
  ),
  a: ({ href, children, ...rest }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline underline-offset-2 hover:brightness-110"
      {...rest}
    >
      {children}
    </a>
  ),
  // Inline citation pills: inline `code` (e.g. a filename or `p. 3`) renders as an
  // accent-tinted mono pill. Fenced blocks keep the block chrome.
  code: (props) => (
    <code
      className="rounded-md border border-accent/30 bg-accent/10 px-1.5 py-0.5 font-mono text-[0.8em] text-accent"
      {...props}
    />
  ),
  pre: (props) => (
    <pre
      className="mb-2 overflow-x-auto rounded-control border border-glass-border bg-glass p-3 text-xs [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-foreground"
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
  const chips = !isUser ? consolidateInvocations(toolInvocations ?? []) : [];
  // Agent label is LIVE-only (set by meta frame during stream). Hidden for the
  // default agent — the picker already shows "assistant".
  const agentLabel = !isUser && agent && agent !== DEFAULT_AGENT.name;

  if (isUser) {
    return (
      <li className="flex justify-end gap-3">
        <div className="glass-hi max-w-[80%] whitespace-pre-wrap rounded-card px-4 py-2.5 text-sm text-foreground">
          {content}
        </div>
        <Avatar kind="user" />
      </li>
    );
  }

  return (
    <li className="flex justify-start gap-3">
      <Avatar kind="neo" />
      <div className="flex min-w-0 max-w-[80%] flex-col items-start gap-1.5">
        {agentLabel && (
          <span
            className="font-mono text-[10px] uppercase tracking-wide text-faint"
            aria-label={`Agent: ${agent}`}
          >
            {agent}
          </span>
        )}
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-1.5" aria-label="Tools Neo used">
            {chips.map((t, i) => (
              <ToolChip key={i} invocation={t} />
            ))}
          </div>
        )}
        <div className={cn("text-sm text-foreground", pending && "text-muted-foreground")}>
          {pending ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden />
              Thinking…
            </span>
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

function Avatar({ kind }: { kind: "user" | "neo" }) {
  if (kind === "neo") {
    return (
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-grad shadow-glow"
        aria-hidden
      >
        <Sparkles className="h-4 w-4 text-on-accent" />
      </span>
    );
  }
  return (
    <span
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-glass-hi text-muted-foreground"
      aria-hidden
    >
      <User className="h-4 w-4" />
    </span>
  );
}
