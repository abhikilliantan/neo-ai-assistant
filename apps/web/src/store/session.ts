"use client";

import { create } from "zustand";

export type SessionUser = { id: string; email: string };

type SessionState = {
  user: SessionUser | null;
  accessToken: string | null;
  tenantId: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  setSession: (s: {
    user: SessionUser;
    accessToken: string;
    refreshToken: string;
    tenantId: string | null;
  }) => void;
  updateAccessToken: (accessToken: string, refreshToken: string) => void;
  clearSession: () => void;
  markHydrated: () => void;
};

// ponytail: refresh in localStorage; move to httpOnly cookie when we have a
// session/CSRF story. In memory would lose the session on reload.
const REFRESH_KEY = "neo.refreshToken";

export function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

function storeRefreshToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(REFRESH_KEY, token);
}

function eraseRefreshToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(REFRESH_KEY);
}

export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  accessToken: null,
  tenantId: null,
  isAuthenticated: false,
  isHydrated: false,
  setSession: ({ user, accessToken, refreshToken, tenantId }) => {
    storeRefreshToken(refreshToken);
    set({
      user,
      accessToken,
      tenantId,
      isAuthenticated: true,
      isHydrated: true,
    });
  },
  updateAccessToken: (accessToken, refreshToken) => {
    storeRefreshToken(refreshToken);
    set({ accessToken, isAuthenticated: true });
  },
  clearSession: () => {
    eraseRefreshToken();
    set({
      user: null,
      accessToken: null,
      tenantId: null,
      isAuthenticated: false,
      isHydrated: true,
    });
  },
  markHydrated: () => set({ isHydrated: true }),
}));
