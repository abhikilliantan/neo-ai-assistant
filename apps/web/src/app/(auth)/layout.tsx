import { GuestGuard } from "@/features/auth/guest-guard";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <GuestGuard>
      <div className="flex min-h-screen items-center justify-center bg-muted/20 p-4">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </GuestGuard>
  );
}
