"use client";

import { useEffect } from "react";
import { refresh as apiRefresh } from "@/services/auth";
import { getStoredRefreshToken, useSessionStore } from "@/store/session";

/**
 * Runs once on mount: if a refresh token is persisted, exchange it for a
 * fresh access token and populate the session. Otherwise mark hydrated so
 * guards stop showing the loading state.
 */
export function SessionInit(): null {
  useEffect(() => {
    const token = getStoredRefreshToken();
    if (!token) {
      useSessionStore.getState().markHydrated();
      return;
    }
    apiRefresh(token)
      .then((r) =>
        useSessionStore.getState().setSession({
          user: { id: r.user_id, email: r.email },
          accessToken: r.access_token,
          refreshToken: r.refresh_token,
          tenantId: r.active_tenant_id,
        }),
      )
      .catch(() => useSessionStore.getState().clearSession());
  }, []);
  return null;
}
