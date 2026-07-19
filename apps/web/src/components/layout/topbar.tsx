"use client";

import { LogOut, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { env } from "@/lib/env";
import { logout as apiLogout } from "@/services/auth";
import { getStoredRefreshToken, useSessionStore } from "@/store/session";
import { useUiStore } from "@/store/ui";

export function Topbar() {
  const toggle = useUiStore((s) => s.toggleSidebar);
  const user = useSessionStore((s) => s.user);
  const clearSession = useSessionStore((s) => s.clearSession);
  const router = useRouter();

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
    <header className="flex h-14 items-center gap-4 border-b bg-card px-4">
      <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle sidebar">
        <Menu className="h-4 w-4" />
      </Button>
      <div className="font-semibold">{env.appName}</div>
      <div className="ml-auto flex items-center gap-3">
        {user && <span className="text-sm text-muted-foreground">{user.email}</span>}
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
