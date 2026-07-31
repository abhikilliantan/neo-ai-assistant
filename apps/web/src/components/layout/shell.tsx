import { MobileNav, Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export function Shell({ children }: { children: React.ReactNode }) {
  // Transparent shell so the body's app-bg gradient shows through; the sidebar,
  // topbar and page surfaces are glass panels layered on top.
  //
  // h-[100dvh] (dynamic viewport height) instead of h-screen so the iOS URL bar
  // and on-screen keyboard shrink the layout instead of hiding the pinned
  // composer. Left/right safe-area padding keeps content off the notch in
  // landscape (both env() values are 0 on desktop, so nothing changes there).
  return (
    <div
      className="flex h-[100dvh] w-screen overflow-hidden"
      style={{
        paddingLeft: "env(safe-area-inset-left)",
        paddingRight: "env(safe-area-inset-right)",
      }}
    >
      <Sidebar />
      <MobileNav />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar />
        {/* min-w-0 above lets wide children (tables) scroll internally rather
            than forcing horizontal page overflow. Bottom padding folds in the
            home-indicator safe area (0 on desktop → md:pb unchanged). */}
        <main className="flex-1 overflow-auto p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] md:p-6 md:pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
          {children}
        </main>
      </div>
    </div>
  );
}
