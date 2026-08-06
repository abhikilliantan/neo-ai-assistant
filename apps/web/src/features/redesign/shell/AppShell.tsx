"use client";

import * as React from "react";
import { DemoModeProvider } from "@/features/redesign/components";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

/** App-wide shell: fixed collapsible sidebar + sticky top bar + content slot.
 *  Rendered once by the /neo layout, so collapse + demo-mode state persist
 *  across routes. Demo mode (default ON) hides all sample chips app-wide. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = React.useState(false);
  const toggle = React.useCallback(() => setCollapsed((c) => !c), []);
  const [demoMode, setDemoMode] = React.useState(true);

  return (
    <DemoModeProvider value={demoMode}>
      <div className="flex min-h-screen bg-rd-base text-rd-body">
        <Sidebar collapsed={collapsed} onToggle={toggle} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar
            collapsed={collapsed}
            onToggle={toggle}
            demoMode={demoMode}
            onDemoChange={setDemoMode}
          />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </DemoModeProvider>
  );
}
