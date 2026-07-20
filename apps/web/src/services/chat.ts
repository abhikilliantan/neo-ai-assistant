import type {
  ChatMessage,
  ChatResponse,
  ChatStreamDone,
  ChatStreamError,
  ChatStreamEvent,
} from "@neo/shared-types";
import { env } from "@/lib/env";
import { http } from "@/services/http";
import { clearAndRedirect, refreshOnce } from "@/services/session-refresh";
import { useSessionStore } from "@/store/session";

// Non-streaming fallback — untouched from phase 3a.
export async function sendChat(messages: ChatMessage[]): Promise<ChatResponse> {
  const { data } = await http.post<ChatResponse>("/api/v1/chat", { messages });
  return data;
}

export type StreamCallbacks = {
  // Meta frame arrives first — carries the server-assigned conversation id
  // and the RESOLVED agent name (6i-1). The caller uses `agent` to render
  // a live label; it is NOT persisted.
  onMeta?: (meta: { conversation_id: string; agent: string }) => void;
  onDelta: (content: string) => void;
  // Live "Neo used X" signal (6e-1). Fires once per tool the backend ran
  // mid-turn, BEFORE the final delta frames. Session-only — the caller
  // renders a chip; nothing is sent back to the backend.
  onTool?: (t: { tool_name: string; tool_ok: boolean }) => void;
  onDone: (info: Omit<ChatStreamDone, "type">) => void;
  onError: (err: Omit<ChatStreamError, "type">) => void;
  signal?: AbortSignal;
  conversationId?: string;
  // Optional agent selection (6i-2). Undefined → wire byte-identical to
  // pre-6h (no `agent` key). Backend resolves absent/null → "assistant".
  agent?: string;
};

// Fetch-based streaming client. Axios can't read a chunked response body in
// the browser, so we go direct to fetch + ReadableStream. Auth: Bearer token
// from the session store; on 401 we run the SAME single-flight refresh the
// axios interceptor uses (see services/session-refresh.ts) and retry once.
export async function streamChat(
  messages: ChatMessage[],
  { onMeta, onDelta, onTool, onDone, onError, signal, conversationId, agent }: StreamCallbacks,
): Promise<void> {
  const url = `${env.apiUrl}/api/v1/chat/stream`;
  // Build the body dynamically so `agent` / `conversation_id` are OMITTED
  // (not sent as null / undefined) when not set — keeps the default path's
  // wire shape byte-identical to pre-6h.
  const payload: Record<string, unknown> = { messages };
  if (conversationId) payload.conversation_id = conversationId;
  if (agent) payload.agent = agent;
  const body = JSON.stringify(payload);

  const doFetch = (token: string | null): Promise<Response> =>
    fetch(url, {
      method: "POST",
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Request-ID": crypto.randomUUID(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body,
    });

  let token = useSessionStore.getState().accessToken;
  let response: Response;
  try {
    response = await doFetch(token);
    if (response.status === 401) {
      const refreshed = await refreshOnce();
      if (!refreshed) {
        clearAndRedirect();
        onError({ code: "unauthorized", message: "Session expired." });
        return;
      }
      token = refreshed;
      response = await doFetch(token);
      if (response.status === 401) {
        clearAndRedirect();
        onError({ code: "unauthorized", message: "Session expired." });
        return;
      }
    }
  } catch (e) {
    if (isAbort(e)) return;
    onError({ code: "network_error", message: (e as Error).message || "Network error." });
    return;
  }

  if (!response.ok || !response.body) {
    const { code, message } = await readErrorEnvelope(response);
    onError({ code, message });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = parseSseFrame(raw);
        if (!event) continue;
        if (event.type === "meta")
          onMeta?.({ conversation_id: event.conversation_id, agent: event.agent });
        else if (event.type === "delta") onDelta(event.content);
        else if (event.type === "tool")
          onTool?.({ tool_name: event.tool_name, tool_ok: event.tool_ok });
        else if (event.type === "done") {
          onDone({ model: event.model, usage: event.usage, finish_reason: event.finish_reason });
          return;
        } else if (event.type === "error") {
          onError({ code: event.code, message: event.message });
          return;
        }
      }
    }
  } catch (e) {
    if (isAbort(e)) return;
    onError({ code: "stream_error", message: (e as Error).message || "Stream error." });
  } finally {
    // ponytail: releaseLock is idempotent-enough here — cancel() would abort mid-frame
    // and we only reach finally after normal completion, error, or abort.
    reader.releaseLock();
  }
}

function parseSseFrame(raw: string): ChatStreamEvent | null {
  // SSE: one event = lines; data-lines joined with "\n". We ignore other fields.
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  try {
    return JSON.parse(dataLines.join("\n")) as ChatStreamEvent;
  } catch {
    return null;
  }
}

async function readErrorEnvelope(response: Response): Promise<{ code: string; message: string }> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const err = body?.error;
    if (err?.code || err?.message) {
      return { code: err.code ?? "http_error", message: err.message ?? `HTTP ${response.status}` };
    }
  } catch {
    // fall through
  }
  return { code: "http_error", message: `HTTP ${response.status}` };
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}
