// Intraday (live-ish) data written to Supabase by the cloud cron
// (system_status['intraday']). Timestamps are UTC "YYYY-MM-DD HH:MM".

export type LiveSnapshot = Record<string, { level: number; chg_1d: number }>;
export type LiveBreadth = {
  advancers?: number;
  decliners?: number;
  turnover_bn_try?: number;
};
export type LiveMover = {
  ticker: string;
  title: string;
  price: number;
  chg_pct: number;
  turnover_mn: number;
  vol_vs_20d: number;
};
export type Intraday = {
  ts: string;
  snapshot?: LiveSnapshot;
  breadth?: LiveBreadth;
  movers?: Record<string, LiveMover[]>;
};

// Return the intraday payload only if it is recent enough to show as
// "live", else null so callers fall back to nightly data.
export function freshIntraday(
  raw: unknown,
  maxAgeMin = 25
): Intraday | null {
  const i = raw as Intraday | undefined;
  if (!i || !i.ts) return null;
  const t = Date.parse(i.ts.replace(" ", "T") + ":00Z"); // treat as UTC
  if (Number.isNaN(t)) return null;
  return Date.now() - t < maxAgeMin * 60_000 ? i : null;
}
