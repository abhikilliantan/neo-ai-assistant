import { Sparkles } from "lucide-react";
import { env } from "@/lib/env";

// Shared chrome for the auth screens: a centered glass card over the app-bg
// gradient, with a gradient logo tile and product name. Login/register drop
// their form + footer into it so both stay visually identical.
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="glass rounded-card p-6 shadow-glow sm:p-8">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-card bg-accent-grad shadow-glow">
          <Sparkles className="h-6 w-6 text-on-accent" aria-hidden />
        </span>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">{title}</h1>
          <p className="text-xs font-medium uppercase tracking-wider text-faint">{env.appName}</p>
        </div>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
      {footer && <div className="mt-4 text-center text-sm text-muted-foreground">{footer}</div>}
    </div>
  );
}
