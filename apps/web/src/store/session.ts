import { create } from "zustand";

type SessionState = {
  // Placeholder — no auth yet.
  userId: string | null;
  setUserId: (id: string | null) => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  userId: null,
  setUserId: (userId) => set({ userId }),
}));
