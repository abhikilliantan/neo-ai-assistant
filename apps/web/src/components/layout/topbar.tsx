"use client";

import { LogOut, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { env } from "@/lib/env";
import { logout as apiLogout } from "@/services/auth";
import { getStoredRefreshToken, useSessionStore } from "@/store/session";
import { useUiStore } from "@/store/ui";

export function Topbar() {
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const openMobileNav = useUiStore((s) => s.openMobileNav);
  const user = useSessionStore((s) => s.user);
  const clearSession = useSessionStore((s) => s.clearSession);
  const router = useRouter();

  // One ☰ button, two meanings: on desktop (md+) it collapses the fixed rail;
  // on mobile it opens the slide-over drawer. matchMedia('md') decides at click
  // time so the two states never interfere.
  function handleMenu() {
    if (typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches) {
      toggleSidebar();
    } else {
      openMobileNav();
    }
  }

  async function handleLogout() {
    const token = getStoredRefreshToken();
    if (token) {
      try {
        await apiLogout(token);
      } catch {
        // Best-effort; server-side revoke is idempotent and non-critical here.
      }
    }
    clearSession();
    router.replace("/login");
  }

  return (
    <header className="flex h-14 items-center gap-3 border-b border-glass-border bg-glass px-3 backdrop-blur-xl backdrop-saturate-150">
      <Button variant="ghost" size="icon" onClick={handleMenu} aria-label="Toggle navigation">
        <Menu className="h-4 w-4" />
      </Button>
      <div className="font-semibold tracking-tight text-foreground">{env.appName}</div>
      <div className="ml-auto flex items-center gap-2">
        {user && (
          <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
        )}
        <ThemeToggle />
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          aria-label="Log out"
          className="gap-2"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Log out</span>
        </Button>
      </div>
    </header>
  );
}
