"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  CheckSquare,
  FileText,
  MoreHorizontal,
  Send,
  Sparkles,
  Telescope,
  User,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@neo/shared-types";
import { sendChat } from "@/services/chat";
import { getConversation } from "@/services/conversations";
import { useSessionStore } from "@/store/session";
import { ConversationsRail } from "./ConversationsRail";
import { ContextRail } from "./ContextRail";
import { parseProjectStatus, ProjectStatusCard, stripStatusBlock } from "./ProjectStatusCard";

// This page pins every turn to the grounded project_analyst agent — its
// answers come from dataset queries, which is what the status card renders.
const AGENT = "project_analyst";

const QUICK_QUESTIONS = [
  "What is Bidco project status?",
  "Which projects are delayed?",
  "How much cash do we have?",
  "Which employees need attention?",
];

const FOLLOW_UPS = [
  "Show detailed timeline",
  "Who are the key stakeholders?",
  "What are the critical risks?",
  "Compare with other projects",
];

// Composer toolbar. None map to a discrete backend endpoint today (Analyze Data
// runs as an LLM tool inside the turn, not a button), so all are disabled with
// an honest tooltip — same discipline as the old composer's Paperclip/Mic.
const TOOLS: Array<{ icon: LucideIcon; label: string }> = [
  { icon: Telescope, label: "Deep Research" },
  { icon: BarChart3, label: "Analyze Data" },
  { icon: FileText, label: "Generate Report" },
  { icon: CheckSquare, label: "Create Task" },
];

type UiMessage = ChatMessage;

function greetingName(email: string | undefined): string | null {
  if (!email) return null;
  const local = email.split("@")[0]?.split(/[._-]/)[0];
  if (!local) return null;
  return local.charAt(0).toUpperCase() + local.slice(1);
}

function timeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 18) return "afternoon";
  return "evening";
}

export function AiChatView() {
  const queryClient = useQueryClient();
  const email = useSessionStore((s) => s.user?.email);

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
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

  // The one send path — used by the composer, quick-question chips, and
  // follow-up chips. Mirrors the existing chat's optimistic flow: append the
  // user bubble + a pending assistant bubble, then swap in the real answer.
  const sendText = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) return;
      setError(null);
      setDraft("");

      const requestHistory: ChatMessage[] = messages
        .map(({ role, content }) => ({ role, content }))
        .concat({ role: "user", content: trimmed });
      setMessages([
        ...messages,
        { role: "user", content: trimmed },
        { role: "assistant", content: "" },
      ]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      void (async () => {
        try {
          const res = await sendChat(requestHistory, {
            signal: controller.signal,
            conversationId: activeConversationId ?? undefined,
            agent: AGENT,
          });
          setActiveConversationId((prev) => prev ?? res.conversation_id);
          setMessages((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { role: "assistant", content: res.message.content };
            }
            return next;
          });
          setStreaming(false);
          abortRef.current = null;
          void queryClient.invalidateQueries({ queryKey: ["conversations"] });
        } catch (e) {
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
    },
    [messages, streaming, activeConversationId, queryClient],
  );

  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content ?? null;
  const hasAssistantReply = messages.some((m) => m.role === "assistant" && m.content.trim() !== "");
  const name = greetingName(email);

  return (
    <div className="mx-auto grid h-[calc(100dvh-7rem)] max-w-[1700px] grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[288px_minmax(0,1fr)_352px]">
      <ConversationsRail
        className="hidden xl:flex"
        activeConversationId={activeConversationId}
        onNewChat={startNewChat}
        onSelect={(id) => void loadConversation(id)}
      />

      {/* Center — the real chat */}
      <section className="flex min-h-0 flex-col gap-3">
        {/* Quick questions */}
        <div className="flex flex-wrap gap-2">
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => sendText(q)}
              disabled={streaming}
              className="rounded-full border border-rd-border bg-rd-panel/60 px-3.5 py-1.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading disabled:cursor-not-allowed disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Chat panel */}
        <div className="glow-card flex min-h-0 flex-1 flex-col overflow-hidden p-0">
          <header className="flex items-center gap-3 border-b border-rd-border px-5 py-4">
            <span className="gradient-ring relative flex h-9 w-9 items-center justify-center rounded-xl bg-rd-card">
              <Sparkles className="h-4 w-4 text-rd-cyan" aria-hidden />
            </span>
            <h2 className="text-base font-semibold text-rd-heading">NEO AI Assistant</h2>
            <span className="rounded-full border border-rd-violet/40 bg-rd-violet/10 px-2.5 py-0.5 text-[11px] font-medium text-rd-violet">
              Powered by NEO Intelligence
            </span>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-5 overflow-auto px-5 py-5">
            {/* Persistent greeting */}
            <AssistantRow>
              <p className="text-sm text-rd-heading">
                Good {timeOfDay()}
                {name ? `, ${name}` : ""}! <span aria-hidden>👋</span>
              </p>
              <p className="mt-1 text-sm text-rd-body">
                I have analyzed your enterprise data across all systems. How can I help you today?
              </p>
            </AssistantRow>

            {loadingHistory && <p className="text-sm text-rd-muted">Loading conversation…</p>}

            {messages.map((m, i) => {
              const pending =
                streaming &&
                i === messages.length - 1 &&
                m.role === "assistant" &&
                m.content === "";
              return <MessageBubble key={i} role={m.role} content={m.content} pending={pending} />;
            })}

            {/* Follow-up chips appear once there's a real answer */}
            {hasAssistantReply && !streaming && (
              <div className="flex flex-wrap gap-2 pt-1">
                {FOLLOW_UPS.map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => sendText(f)}
                    className="rounded-full border border-rd-border bg-rd-panel/60 px-3 py-1.5 text-xs font-medium text-rd-body transition-colors hover:border-rd-border-hover hover:text-rd-heading"
                  >
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-control border border-rd-rose/40 bg-rd-rose/10 px-3 py-2 text-xs text-rd-rose"
          >
            {error}
          </p>
        )}

        {/* Composer */}
        <div className="glow-card p-3">
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendText(draft);
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask NEO anything about your enterprise…"
              aria-label="Message"
              disabled={streaming || loadingHistory}
              className="h-11 min-w-0 flex-1 rounded-control border border-rd-border bg-rd-panel/60 px-4 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={streaming || loadingHistory || draft.trim() === ""}
              aria-label="Send message"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-rd-grad text-white shadow-[0_6px_20px_-6px_var(--rd-glow)] transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Send className="h-4 w-4" aria-hidden />
            </button>
          </form>

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {TOOLS.map((t) => (
              <button
                key={t.label}
                type="button"
                disabled
                title={`${t.label} — coming soon`}
                className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-control border border-rd-border bg-rd-panel/40 px-2.5 py-1.5 text-xs font-medium text-rd-muted opacity-70"
              >
                <t.icon className="h-3.5 w-3.5" aria-hidden />
                {t.label}
              </button>
            ))}
            <button
              type="button"
              disabled
              title="More tools — coming soon"
              aria-label="More tools — coming soon"
              className="inline-flex h-8 w-8 cursor-not-allowed items-center justify-center rounded-control border border-rd-border bg-rd-panel/40 text-rd-muted opacity-70"
            >
              <MoreHorizontal className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-rd-muted">
          NEO can make mistakes. Verify important information.
        </p>
      </section>

      <ContextRail className="hidden min-h-0 overflow-auto lg:block" lastQuestion={lastQuestion} />
    </div>
  );
}

function AssistantRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-start gap-3">
      <NeoAvatar />
      <div className="min-w-0 max-w-[85%] rounded-2xl rounded-tl-sm border border-rd-border bg-rd-panel/60 px-4 py-3">
        {children}
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
  if (role === "user") {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm border border-rd-cyan/30 bg-rd-cyan/10 px-4 py-2.5 text-sm text-rd-heading">
          {content}
        </div>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-rd-border bg-rd-panel text-rd-muted">
          <User className="h-4 w-4" aria-hidden />
        </span>
      </div>
    );
  }

  const status = !pending ? parseProjectStatus(content) : null;

  return (
    <div className="flex justify-start gap-3">
      <NeoAvatar />
      <div className="flex min-w-0 max-w-[92%] flex-col gap-3">
        {pending ? (
          <span className="inline-flex items-center gap-2 text-sm text-rd-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rd-cyan" aria-hidden />
            Thinking…
          </span>
        ) : status ? (
          <>
            {stripStatusBlock(content) && (
              <Markdown className="text-sm text-rd-body">{stripStatusBlock(content)}</Markdown>
            )}
            <ProjectStatusCard data={status} />
          </>
        ) : (
          <Markdown className="text-sm text-rd-body">{content}</Markdown>
        )}
      </div>
    </div>
  );
}

function NeoAvatar() {
  return (
    <span
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rd-grad"
      aria-hidden
    >
      <Sparkles className="h-4 w-4 text-white" />
    </span>
  );
}

// Dark-theme markdown for assistant answers. Inline `code` renders as an accent
// citation pill — grounded project_analyst answers cite filenames / sections in
// backticks, so this keeps citations visible.
const MARKDOWN_COMPONENTS: Components = {
  p: (props) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
  strong: (props) => <strong className="font-semibold text-rd-heading" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  ul: (props) => <ul className="mb-2 list-disc pl-5 last:mb-0" {...props} />,
  ol: (props) => <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props} />,
  li: (props) => <li className="mb-0.5" {...props} />,
  h1: (props) => <h1 className="mb-2 mt-1 text-base font-semibold text-rd-heading" {...props} />,
  h2: (props) => <h2 className="mb-2 mt-1 text-sm font-semibold text-rd-heading" {...props} />,
  h3: (props) => <h3 className="mb-1 mt-1 text-sm font-semibold text-rd-heading" {...props} />,
  table: (props) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm" {...props} />
    </div>
  ),
  th: (props) => (
    <th className="border-b border-rd-border px-2 py-1 font-semibold text-rd-heading" {...props} />
  ),
  td: (props) => <td className="border-b border-rd-border/60 px-2 py-1" {...props} />,
  blockquote: (props) => (
    <blockquote
      className="mb-2 border-l-2 border-rd-cyan/40 pl-3 italic text-rd-muted"
      {...props}
    />
  ),
  a: ({ href, children, ...rest }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-rd-cyan underline underline-offset-2 hover:brightness-110"
      {...rest}
    >
      {children}
    </a>
  ),
  code: (props) => (
    <code
      className="rounded-md border border-rd-cyan/30 bg-rd-cyan/10 px-1.5 py-0.5 font-mono text-[0.8em] text-rd-cyan"
      {...props}
    />
  ),
  pre: (props) => (
    <pre
      className="mb-2 overflow-x-auto rounded-control border border-rd-border bg-rd-panel p-3 text-xs [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-rd-body"
      {...props}
    />
  ),
};

function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
