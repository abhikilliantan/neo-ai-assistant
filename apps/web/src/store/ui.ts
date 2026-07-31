import { create } from "zustand";

type UiState = {
  // Desktop-only: collapses the fixed sidebar between full (w-60) and icons (w-16).
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebar: (open: boolean) => void;
  // Mobile-only (< md): the slide-over nav drawer. Kept separate from
  // sidebarOpen so the ☰ button can mean "collapse" on desktop and "open
  // drawer" on mobile without the two states fighting each other.
  mobileNavOpen: boolean;
  openMobileNav: () => void;
  closeMobileNav: () => void;
  // Mobile-only (< md): the Chat screen's conversation-history drawer. Opening
  // either mobile drawer closes the other so only one is ever on screen.
  conversationDrawerOpen: boolean;
  openConversationDrawer: () => void;
  closeConversationDrawer: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebar: (open) => set({ sidebarOpen: open }),
  mobileNavOpen: false,
  openMobileNav: () => set({ mobileNavOpen: true, conversationDrawerOpen: false }),
  closeMobileNav: () => set({ mobileNavOpen: false }),
  conversationDrawerOpen: false,
  openConversationDrawer: () => set({ conversationDrawerOpen: true, mobileNavOpen: false }),
  closeConversationDrawer: () => set({ conversationDrawerOpen: false }),
}));
