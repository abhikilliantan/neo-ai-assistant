"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, LayoutDashboard, MessageSquare, Settings } from "lucide-react";
import { cn } from "@/lib/cn";
import { useUiStore } from "@/store/ui";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const open = useUiStore((s) => s.sidebarOpen);
  return (
    <aside className={cn("border-r bg-card transition-all", open ? "w-60" : "w-16")}>
      <div className="flex h-14 items-center px-4 font-semibold">Neo</div>
      <nav className="flex flex-col gap-1 p-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active ? "bg-muted font-medium" : "hover:bg-muted",
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
