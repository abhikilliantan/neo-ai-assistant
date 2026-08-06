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

/** Compact currency for revenue tiles, e.g. $1.2M / $840K / $512. */
export function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
}
