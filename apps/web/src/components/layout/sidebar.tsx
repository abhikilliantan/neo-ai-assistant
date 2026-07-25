"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FileText, LayoutDashboard, MessageSquare, Settings } from "lucide-react";
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
        "border-r border-glass-border bg-glass backdrop-blur-xl backdrop-saturate-150 transition-all",
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
