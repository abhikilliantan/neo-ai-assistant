"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUiStore } from "@/store/ui";
import { env } from "@/lib/env";

export function Topbar() {
  const toggle = useUiStore((s) => s.toggleSidebar);
  return (
    <header className="flex h-14 items-center gap-4 border-b bg-card px-4">
      <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle sidebar">
        <Menu className="h-4 w-4" />
      </Button>
      <div className="font-semibold">{env.appName}</div>
    </header>
  );
}
