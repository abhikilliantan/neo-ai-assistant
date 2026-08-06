// Small display helpers for the redesign kit. "Round all displayed numbers."

/** Round to a fixed number of decimals (default 0) and strip trailing zeros. */
export function round(n: number, decimals = 0): string {
  return Number(n.toFixed(decimals)).toLocaleString("en-US");
}

/** A signed, rounded delta string, e.g. +4.2 / -1 / 0. */
export function formatDelta(n: number, decimals = 1): string {
  const r = Number(n.toFixed(decimals));
  return `${r > 0 ? "+" : ""}${r.toLocaleString("en-US")}`;
}

/** Compact currency for revenue tiles, e.g. $1.28M / $542K / $512.
 *  Hand-rolled (not Intl compact notation) so server and client agree — ICU
 *  compact formatting varies by Node/browser CLDR version and breaks hydration. */
export function formatCurrency(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${round(n / 1_000_000, 2)}M`;
  if (abs >= 1_000) return `$${round(n / 1_000, 0)}K`;
  return `$${round(n, 0)}`;
}
