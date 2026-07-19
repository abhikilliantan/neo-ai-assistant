// Single-flight access-token refresh, shared by the axios interceptor (services/http.ts)
// and the fetch-based streaming client (services/chat.ts) so N concurrent 401s
// across both paths still collapse into one refresh call.

import { getStoredRefreshToken, useSessionStore } from "@/store/session";

let refreshPromise: Promise<string | null> | null = null;

export async function refreshOnce(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const stored = getStoredRefreshToken();
    if (!stored) return null;
    try {
      const { refresh } = await import("@/services/auth");
      const r = await refresh(stored);
      useSessionStore.getState().setSession({
        user: { id: r.user_id, email: r.email },
        accessToken: r.access_token,
        refreshToken: r.refresh_token,
        tenantId: r.active_tenant_id,
      });
      return r.access_token;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export function clearAndRedirect(): void {
  useSessionStore.getState().clearSession();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}
