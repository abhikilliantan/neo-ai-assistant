"use client";

import { cn } from "@/lib/cn";

/**
 * Mobile-only (< md) slide-over drawer: a dimmed tap-to-dismiss backdrop plus a
 * panel that slides in from one edge. Hidden entirely at md+. Shared by the nav
 * drawer (MobileNav) and the chat conversation-history drawer so both behave
 * and animate identically. Purely presentational — open state + handlers live
 * in the caller (useUiStore).
 */
export function MobileDrawer({
  open,
  onClose,
  label,
  side = "left",
  children,
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  side?: "left" | "right";
  children: React.ReactNode;
}) {
  const isLeft = side === "left";
  return (
    <div
      className={cn("fixed inset-0 z-50 md:hidden", open ? "" : "pointer-events-none")}
      aria-hidden={!open}
    >
      {/* Tap-to-dismiss backdrop */}
      <button
        type="button"
        aria-label={`Close ${label}`}
        tabIndex={open ? 0 : -1}
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-black/50 transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0",
        )}
      />
      {/* Sliding panel */}
      <div
        role="dialog"
        aria-label={label}
        aria-modal={open}
        className={cn(
          "absolute inset-y-0 flex w-64 max-w-[85%] flex-col bg-glass-hi backdrop-blur-xl backdrop-saturate-150 transition-transform duration-200",
          isLeft
            ? "left-0 border-r border-glass-border-strong"
            : "right-0 border-l border-glass-border-strong",
          open ? "translate-x-0" : isLeft ? "-translate-x-full" : "translate-x-full",
        )}
        style={
          isLeft
            ? { paddingLeft: "env(safe-area-inset-left)" }
            : { paddingRight: "env(safe-area-inset-right)" }
        }
      >
        {children}
      </div>
    </div>
  );
}
