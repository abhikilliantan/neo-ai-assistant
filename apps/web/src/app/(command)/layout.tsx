import { AuthGuard } from "@/features/auth/auth-guard";

// The Command Center is a full-bleed surface with its own bespoke shell
// (CommandCenter renders sidebar + topbar), so it does NOT use the standard app
// Shell — only the auth gate wraps it.
export default function CommandLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
