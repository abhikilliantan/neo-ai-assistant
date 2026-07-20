// Framework-free transport contracts shared across web + tooling.
// No business types — those live in feature packages.

export type ApiEnvelope<T> = {
  data: T;
  requestId: string;
};

export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

// Backend maps domain errors into this shape via core/exceptions.py.
export type ApiErrorEnvelope = {
  error: ApiError;
};

export type Pagination = {
  page: number;
  pageSize: number;
  total: number;
};

export type HealthStatus = {
  status: "ok" | "degraded";
  version: string;
};

// --- auth (mirrors backend AuthResponse) ---
export type AuthResponse = {
  user_id: string;
  email: string;
  active_tenant_id: string | null;
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type RegisterRequest = {
  email: string;
  password: string;
  organization_name?: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type RefreshRequest = {
  refresh_token: string;
};

// --- chat (mirrors backend app/application/ports/chat.py) ---
export type ChatRole = "system" | "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type ChatUsage = {
  prompt_tokens: number;
  completion_tokens: number;
};

export type ChatRequest = {
  messages: ChatMessage[];
};

// Tools the provider ran during THIS turn — live UI signal only. Never
// persisted; reloading a conversation via /conversations/{id} does not
// carry these. `name` is a stable identifier ("search_memory") that the
// UI turns into a human label ("Searched your memories"); `ok` is
// `!is_error` from the tool execution. Arguments are deliberately omitted
// (a search query can carry sensitive text).
export type ToolInvocation = { name: string; ok: boolean };

export type ChatResponse = {
  message: ChatMessage;
  model: string;
  usage: ChatUsage | null;
  // Additive default; omitted / empty array when no tools ran this turn.
  tool_invocations?: ToolInvocation[];
  // Resolved agent name (6i-1). Always present; equals `body.agent or "assistant"`.
  agent: string;
};

// SSE frames from POST /api/v1/chat/stream. Backend emits delta / done / tool
// via the provider; error frames come from the endpoint when a provider
// raises after headers were sent. Discriminate on `type`.
export type ChatStreamMeta = { type: "meta"; conversation_id: string; agent: string };
export type ChatStreamDelta = { type: "delta"; content: string };
export type ChatStreamDone = {
  type: "done";
  model: string;
  usage: ChatUsage | null;
  finish_reason: string;
};
// Fires once per tool the provider ran mid-turn (6e-1). The UI renders a
// small chip; the frame is NOT accumulated into the assistant content.
export type ChatStreamTool = { type: "tool"; tool_name: string; tool_ok: boolean };
export type ChatStreamError = { type: "error"; code: string; message: string };
export type ChatStreamEvent =
  ChatStreamMeta | ChatStreamDelta | ChatStreamDone | ChatStreamTool | ChatStreamError;

// --- conversation persistence (mirrors backend /api/v1/conversations) ---
export type ConversationSummary = {
  id: string;
  title: string | null;
  last_message_at: string | null;
  created_at: string;
};

export type ConversationMessage = {
  id: string;
  role: ChatRole;
  content: string;
  model: string | null;
  created_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ConversationMessage[];
};

// --- memory & preferences (mirrors backend /api/v1/memories + /preferences) ---
export type Memory = {
  id: string;
  content: string;
  kind: string;
  source: string | null;
  created_at: string;
};

// Backend column is JSONB — value is any valid JSON, so `unknown` at the boundary.
export type Preference = {
  key: string;
  value: unknown;
};
