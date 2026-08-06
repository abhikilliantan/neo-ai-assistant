import { notFound } from "next/navigation";
import { AuthGuard } from "@/features/auth/auth-guard";
import { AppShell } from "@/features/redesign/shell";

// Redesign shell (Phase 1) — internal preview, hidden (404) in production so it
// can't ship over the live app until the redesign is finished.
export const metadata = { title: "NEO — AI Operating System" };

export default function NeoLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === "production") notFound();
  // AuthGuard gates rendering until SessionInit has hydrated the session from
  // the stored refresh token. Without it, the page's React Query calls fire
  // before hydration and race SessionInit's refresh — and since the backend
  // rotates+revokes refresh tokens, that race invalidates the token and bounces
  // to /login. Matches the (app)/(command) layouts.
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
