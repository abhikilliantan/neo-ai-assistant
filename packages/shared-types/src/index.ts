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

export type ChatResponse = {
  message: ChatMessage;
  model: string;
  usage: ChatUsage | null;
};

// SSE frames from POST /api/v1/chat/stream. Backend emits delta/done via the
// provider; error frames come from the endpoint when a provider raises after
// headers were sent. Discriminate on `type`.
export type ChatStreamDelta = { type: "delta"; content: string };
export type ChatStreamDone = {
  type: "done";
  model: string;
  usage: ChatUsage | null;
  finish_reason: string;
};
export type ChatStreamError = { type: "error"; code: string; message: string };
export type ChatStreamEvent = ChatStreamDelta | ChatStreamDone | ChatStreamError;
