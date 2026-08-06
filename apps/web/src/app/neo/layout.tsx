import { notFound } from "next/navigation";
import { AppShell } from "@/features/redesign/shell";

// Redesign shell (Phase 1) — internal preview, hidden (404) in production so it
// can't ship over the live app until the redesign is finished.
export const metadata = { title: "NEO — AI Operating System" };

export default function NeoLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === "production") notFound();
  return <AppShell>{children}</AppShell>;
}
