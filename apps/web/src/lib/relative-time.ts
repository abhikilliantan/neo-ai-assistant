// Compact relative timestamp for sidebar rows.
//   < 60s   → "just now"
//   < 60m   → "5m"
//   < 24h   → "2h"
//   < 7d    → "3d"
//   else    → "Jan 15" (or "Jan 15, 2024" if a different year)

const SHORT_MONTH: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
const SHORT_MONTH_YEAR: Intl.DateTimeFormatOptions = {
  month: "short",
  day: "numeric",
  year: "numeric",
};

export function formatRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d`;
  const opts = then.getFullYear() === now.getFullYear() ? SHORT_MONTH : SHORT_MONTH_YEAR;
  return then.toLocaleDateString(undefined, opts);
}
