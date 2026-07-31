"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FileText, LayoutDashboard, MessageSquare, Settings } from "lucide-react";
import { MobileDrawer } from "@/components/layout/mobile-drawer";
import { cn } from "@/lib/cn";
import { useUiStore } from "@/store/ui";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/datasets", label: "Datasets", icon: Database },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const open = useUiStore((s) => s.sidebarOpen);
  return (
    <aside
      className={cn(
        // Hidden on mobile (< md) — small screens use <MobileNav /> instead, so
        // the main content gets the full width with no permanent sidebar gutter.
        "hidden shrink-0 border-r border-glass-border bg-glass backdrop-blur-xl backdrop-saturate-150 transition-all md:block",
        open ? "w-60" : "w-16",
      )}
    >
      <div className="flex h-14 items-center gap-2 px-4">
        <span className="h-6 w-6 shrink-0 rounded-md bg-accent-grad shadow-glow" aria-hidden />
        {open && <span className="font-semibold tracking-tight text-foreground">Neo</span>}
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-control px-3 py-2 text-sm transition-colors",
                active
                  ? "glass-hi font-medium text-foreground"
                  : "text-muted-foreground hover:bg-glass hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {open && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

/**
 * Mobile-only (< md) slide-over nav drawer. Toggled by the ☰ button in the
 * Topbar, dismissed by tapping the backdrop or any nav item. Hidden entirely
 * on md+, where <Sidebar /> is the permanent fixed rail. Shares the `nav`
 * array above so the two never drift.
 */
export function MobileNav() {
  const pathname = usePathname();
  const open = useUiStore((s) => s.mobileNavOpen);
  const close = useUiStore((s) => s.closeMobileNav);

  return (
    <MobileDrawer open={open} onClose={close} label="Navigation" side="left">
      <div className="flex h-14 items-center gap-2 px-4">
        <span className="h-6 w-6 shrink-0 rounded-md bg-accent-grad shadow-glow" aria-hidden />
        <span className="font-semibold tracking-tight text-foreground">Neo</span>
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              onClick={close}
              className={cn(
                "flex items-center gap-3 rounded-control px-3 py-3 text-sm transition-colors",
                active
                  ? "glass-hi font-medium text-foreground"
                  : "text-muted-foreground hover:bg-glass hover:text-foreground",
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </MobileDrawer>
  );
}
