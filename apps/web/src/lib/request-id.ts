/**
 * Generates an X-Request-ID. Request IDs are non-cryptographic correlation
 * tokens, so a Math.random fallback is fine — and necessary: crypto.randomUUID()
 * only exists in secure contexts (https / localhost), so it throws when the app
 * is served over a plain-http origin (e.g. a Tailscale IP or reverse proxy).
 */
export const requestId = (): string =>
  globalThis.crypto?.randomUUID?.() ??
  `req-${Date.now()}-${Math.random().toString(16).slice(2)}${Math.random().toString(16).slice(2)}`;
