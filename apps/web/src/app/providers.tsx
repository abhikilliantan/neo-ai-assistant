"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { SessionInit } from "@/features/auth/session-init";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );
  return (
    // attribute="data-theme" + defaultTheme="dark" + enableSystem=false: next-themes
    // writes data-theme onto <html> before paint (its inline script), so with
    // suppressHydrationWarning on <html> there is no flash-of-wrong-theme on reload.
    <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={client}>
        <SessionInit />
        {children}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
