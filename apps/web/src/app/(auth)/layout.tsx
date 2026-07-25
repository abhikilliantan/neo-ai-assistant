import { GuestGuard } from "@/features/auth/guest-guard";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  // Transparent over the body's app-bg gradient; the form is a centered glass card.
  return (
    <GuestGuard>
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </GuestGuard>
  );
}
