import { ExecBriefingView } from "@/features/redesign/exec-briefing/ExecBriefingView";

// Static route wins over the [section] placeholder.
export const metadata = { title: "Executive Briefing — NEO" };
// "Today's date" must reflect the request, not build time.
export const dynamic = "force-dynamic";

// Server-computed real date, passed to the client view so both sides render the
// same string (a client-side new Date() would hydration-mismatch).
export default function ExecutiveBriefingPage() {
  const todayLabel = new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(new Date());

  return <ExecBriefingView todayLabel={todayLabel} />;
}
