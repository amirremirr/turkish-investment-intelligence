// Display formatting. All figures are nominal TRY unless noted.

export function pct(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}

export function pctPoints(x: number | null | undefined, digits = 1): string {
  if (x == null || Number.isNaN(x)) return "—";
  const v = (x * 100).toFixed(digits);
  return `${x >= 0 ? "+" : ""}${v}pp`;
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x == null || Number.isNaN(x)) return "—";
  return x.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function tryBn(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "—";
  if (Math.abs(x) >= 1e12) return `₺${(x / 1e12).toFixed(2)}T`;
  if (Math.abs(x) >= 1e9) return `₺${(x / 1e9).toFixed(2)}B`;
  if (Math.abs(x) >= 1e6) return `₺${(x / 1e6).toFixed(0)}M`;
  return `₺${x.toFixed(0)}`;
}

export function intFmt(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "—";
  return Math.round(x).toLocaleString("en-US");
}

// sign class for +/- coloring
export function signClass(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "text-muted";
  return x > 0 ? "text-pos" : x < 0 ? "text-neg" : "text-muted";
}
