import type { Metadata } from "next";
import "@/styles/globals.css";
import { Providers } from "@/app/providers";
import { env } from "@/lib/env";

export const metadata: Metadata = {
  title: env.appName,
  description: "Enterprise AI Operating System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* suppressHydrationWarning here too: browser extensions (Grammarly, etc.)
          inject attributes onto <body> before hydration, and the <html>-level
          flag does not cover descendants. */}
      <body className="antialiased" suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
