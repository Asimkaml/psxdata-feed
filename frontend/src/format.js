const dash = "—";

export const fmtPrice = (v) =>
  v == null ? dash : v.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtPct = (v, signed = false) =>
  v == null ? dash : `${signed && v > 0 ? "+" : ""}${v.toFixed(2)}%`;

export const fmtNum = (v, digits = 2) => (v == null ? dash : v.toFixed(digits));

// Compact PKR amounts: 1.2T / 345.6B / 12.3M
export function fmtCompact(v) {
  if (v == null) return dash;
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}

export const titleCase = (s) =>
  typeof s === "string" && s ? s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : dash;
