import { sql } from "./db";

// postgres.js returns numeric/bigint as strings to preserve precision;
// coerce to JS numbers for our display purposes.
const n = (x: unknown): number | null =>
  x == null ? null : Number(x as string);

export type FundRow = {
  code: string;
  title: string | null;
  category: string | null;
  ret_1y: number | null;
  sharpe: number | null;
  max_dd: number | null;
  alpha_annual: number | null;
  aum: number | null;
  skill_score: number | null;
  suitability_score: number | null;
};

export async function getScreenerFunds(): Promise<FundRow[]> {
  const rows = await sql`
    SELECT code, title, category, ret_1y, sharpe, max_dd, alpha_annual,
           aum, skill_score, suitability_score
    FROM dash_quality`;
  return rows.map((r) => ({
    code: r.code,
    title: r.title,
    category: r.category,
    ret_1y: n(r.ret_1y),
    sharpe: n(r.sharpe),
    max_dd: n(r.max_dd),
    alpha_annual: n(r.alpha_annual),
    aum: n(r.aum),
    skill_score: n(r.skill_score),
    suitability_score: n(r.suitability_score),
  }));
}

export type FundDetail = {
  code: string;
  title: string | null;
  category: string | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_6m: number | null;
  ret_1y: number | null;
  excess_1y: number | null;
  beta: number | null;
  ann_vol: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_dd: number | null;
  aum: number | null;
  investors: number | null;
  n_obs: number | null;
  // factor model
  alpha_annual: number | null;
  alpha_t: number | null;
  beta_bist100: number | null;
  beta_gold_try: number | null;
  beta_usdtry: number | null;
  beta_nasdaq_try: number | null;
  r_squared: number | null;
  // scores
  skill_score: number | null;
  suitability_score: number | null;
};

export async function getFund(code: string): Promise<FundDetail | null> {
  const rows = await sql`
    SELECT m.code, m.title, m.category, m.ret_1m, m.ret_3m, m.ret_6m,
           m.ret_1y, m.excess_1y, m.beta, m.ann_vol, m.sharpe, m.sortino,
           m.max_dd, m.aum, m.investors, m.n_obs,
           b.alpha_annual, b.alpha_t, b.beta_bist100, b.beta_gold_try,
           b.beta_usdtry, b.beta_nasdaq_try, b.r_squared,
           q.skill_score, q.suitability_score
    FROM dash_metrics m
    LEFT JOIN dash_betas b ON b.code = m.code
    LEFT JOIN dash_quality q ON q.code = m.code
    WHERE m.code = ${code.toUpperCase()}
    LIMIT 1`;
  if (rows.length === 0) return null;
  const r = rows[0];
  return {
    code: r.code,
    title: r.title,
    category: r.category,
    ret_1m: n(r.ret_1m),
    ret_3m: n(r.ret_3m),
    ret_6m: n(r.ret_6m),
    ret_1y: n(r.ret_1y),
    excess_1y: n(r.excess_1y),
    beta: n(r.beta),
    ann_vol: n(r.ann_vol),
    sharpe: n(r.sharpe),
    sortino: n(r.sortino),
    max_dd: n(r.max_dd),
    aum: n(r.aum),
    investors: n(r.investors),
    n_obs: n(r.n_obs),
    alpha_annual: n(r.alpha_annual),
    alpha_t: n(r.alpha_t),
    beta_bist100: n(r.beta_bist100),
    beta_gold_try: n(r.beta_gold_try),
    beta_usdtry: n(r.beta_usdtry),
    beta_nasdaq_try: n(r.beta_nasdaq_try),
    r_squared: n(r.r_squared),
    skill_score: n(r.skill_score),
    suitability_score: n(r.suitability_score),
  };
}

export async function getFundNav(
  code: string
): Promise<{ date: string; price: number }[]> {
  const rows = await sql`
    SELECT date, price FROM prices
    WHERE code = ${code.toUpperCase()} AND price > 0
    ORDER BY date`;
  return rows.map((r) => ({ date: r.date, price: Number(r.price) }));
}

export type Holding = {
  ticker: string | null;
  name: string | null;
  weight_pct: number | null;
  value: number | null;
  n_funds: number | null; // how many funds hold this ticker (consensus)
};

export async function getFundHoldings(code: string): Promise<Holding[]> {
  const c = code.toUpperCase();
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    ),
    book AS (
      SELECT h.* FROM fund_holdings h
      JOIN latest l ON l.code = h.code AND l.mp = h.period
    ),
    crowd AS (
      SELECT ticker, COUNT(DISTINCT code) AS n_funds FROM book GROUP BY ticker
    )
    SELECT b.ticker, b.name, b.weight_pct, b.value, c.n_funds
    FROM book b
    LEFT JOIN crowd c ON c.ticker = b.ticker
    WHERE b.code = ${c}
    ORDER BY b.weight_pct DESC NULLS LAST`;
  return rows.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    weight_pct: n(r.weight_pct),
    value: n(r.value),
    n_funds: n(r.n_funds),
  }));
}

export type SimilarFund = {
  code: string;
  title: string | null;
  overlap: number; // pp of portfolio in the same stocks at the same weight
  shared: number; // number of common holdings
};

// Holdings overlap between this fund and every other: Σ min(weight) over
// common tickers — the share of portfolio two funds hold identically.
// High overlap = near-clone books (holdings-based herding, independent
// of the return-based closet-index signal).
export async function getSimilarFunds(code: string): Promise<SimilarFund[]> {
  const c = code.toUpperCase();
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    ),
    book AS (
      SELECT h.code, h.ticker, h.weight_pct FROM fund_holdings h
      JOIN latest l ON l.code = h.code AND l.mp = h.period
      WHERE h.weight_pct > 0
    ),
    target AS (SELECT ticker, weight_pct FROM book WHERE code = ${c})
    SELECT b.code, f.title,
           SUM(LEAST(b.weight_pct, t.weight_pct)) AS overlap,
           COUNT(*) AS shared
    FROM book b
    JOIN target t ON t.ticker = b.ticker
    LEFT JOIN funds f ON f.code = b.code
    WHERE b.code <> ${c}
    GROUP BY b.code, f.title
    HAVING SUM(LEAST(b.weight_pct, t.weight_pct)) >= 10
    ORDER BY overlap DESC
    LIMIT 6`;
  return rows.map((r) => ({
    code: r.code,
    title: r.title,
    overlap: Number(r.overlap),
    shared: Number(r.shared),
  }));
}

export async function getFundCodes(limit = 60): Promise<string[]> {
  const rows = await sql`
    SELECT code FROM dash_metrics
    WHERE aum IS NOT NULL ORDER BY aum DESC LIMIT ${limit}`;
  return rows.map((r) => r.code);
}

// --- market-level ---

export type StatusMap = Record<string, unknown>;

export async function getStatus(): Promise<StatusMap> {
  const rows = await sql`SELECT key, value FROM system_status`;
  const out: StatusMap = {};
  for (const r of rows) {
    try {
      out[r.key] = JSON.parse(r.value);
    } catch {
      out[r.key] = r.value;
    }
  }
  return out;
}

export async function getCategoryFlows(): Promise<
  { category: string; net_flow_bn: number }[]
> {
  const rows = await sql`
    SELECT category, net_flow_bn FROM dash_cat_flows
    ORDER BY net_flow_bn DESC`;
  return rows.map((r) => ({
    category: r.category,
    net_flow_bn: Number(r.net_flow_bn),
  }));
}

export async function getSectors(): Promise<
  { sector: string; stocks: number; ret_1d: number; ret_1m: number }[]
> {
  const rows = await sql`
    SELECT sector, stocks, ret_1d, ret_1m FROM dash_sectors
    ORDER BY ret_1d DESC`;
  return rows.map((r) => ({
    sector: r.sector,
    stocks: Number(r.stocks),
    ret_1d: Number(r.ret_1d),
    ret_1m: Number(r.ret_1m),
  }));
}

export async function getMarketAggregate(): Promise<{
  total_aum: number;
  n_funds: number;
}> {
  const rows = await sql`
    SELECT COALESCE(SUM(aum),0) AS total_aum, COUNT(*) AS n_funds
    FROM dash_metrics`;
  return {
    total_aum: Number(rows[0].total_aum),
    n_funds: Number(rows[0].n_funds),
  };
}

export async function getHoldingsCoverage(): Promise<number> {
  // every fund that has ever disclosed a book, not just the latest period
  const rows = await sql`SELECT COUNT(DISTINCT code) AS n FROM fund_holdings`;
  return Number(rows[0].n);
}

// Ownership (which funds hold a stock) is complete; position *weights*
// only parse cleanly for a subset of KAP PDF templates so far. Surface
// that honestly rather than implying every weight is known.
export async function getWeightCoverage(): Promise<{
  withWeights: number;
  total: number;
}> {
  const rows = await sql`
    SELECT COUNT(DISTINCT code) AS total,
           COUNT(DISTINCT code) FILTER (WHERE weight_pct > 0) AS with_weights
    FROM fund_holdings`;
  return {
    withWeights: Number(rows[0].with_weights),
    total: Number(rows[0].total),
  };
}

// --- stock <-> fund explorer ---

export type StockInfo = {
  ticker: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  city: string | null;
};

export async function getStock(ticker: string): Promise<StockInfo | null> {
  const t = ticker.toUpperCase();
  const rows = await sql`
    SELECT ticker, title AS name, sector, industry, city
    FROM stocks WHERE ticker = ${t} LIMIT 1`;
  if (rows.length === 0) return null;
  const r = rows[0];
  return {
    ticker: r.ticker,
    name: r.name,
    sector: r.sector,
    industry: r.industry,
    city: r.city,
  };
}

export type StockOwner = {
  code: string;
  title: string | null;
  category: string | null;
  weight_pct: number | null;
  value: number | null;
  aum: number | null;
};

// Which funds hold this stock in their most recent disclosed book — the
// stock->fund direction the explorer is built around. Funds file KAP
// reports at different times, so "latest" means each fund's own latest
// period (a single global MAX(period) would show only whoever filed
// most recently).
export async function getStockOwners(ticker: string): Promise<StockOwner[]> {
  const t = ticker.toUpperCase();
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    )
    SELECT h.code, f.title, f.category, h.weight_pct, h.value, m.aum
    FROM fund_holdings h
    JOIN latest l ON l.code = h.code AND l.mp = h.period
    LEFT JOIN funds f ON f.code = h.code
    LEFT JOIN dash_metrics m ON m.code = h.code
    WHERE h.ticker = ${t}
    ORDER BY h.weight_pct DESC NULLS LAST`;
  return rows.map((r) => ({
    code: r.code,
    title: r.title,
    category: r.category,
    weight_pct: n(r.weight_pct),
    value: n(r.value),
    aum: n(r.aum),
  }));
}

export type CoveredStock = {
  ticker: string;
  name: string | null;
  sector: string | null;
  n_funds: number;
  avg_weight: number | null;
};

// Every BIST equity held by at least one fund in the latest period —
// the browsable entry point to the explorer, ranked by ownership breadth.
export async function getCoveredStocks(): Promise<CoveredStock[]> {
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    ),
    book AS (
      SELECT h.* FROM fund_holdings h
      JOIN latest l ON l.code = h.code AND l.mp = h.period
    )
    SELECT b.ticker, MAX(s.title) AS name, MAX(s.sector) AS sector,
           COUNT(DISTINCT b.code) AS n_funds, AVG(b.weight_pct) AS avg_weight
    FROM book b
    JOIN stocks s ON s.ticker = b.ticker
    GROUP BY b.ticker
    ORDER BY COUNT(DISTINCT b.code) DESC, MAX(b.weight_pct) DESC NULLS LAST`;
  return rows.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    sector: r.sector,
    n_funds: Number(r.n_funds),
    avg_weight: n(r.avg_weight),
  }));
}

export async function getCrowding(
  limit = 20
): Promise<
  { ticker: string; name: string | null; n_funds: number; avg_weight: number }[]
> {
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    ),
    book AS (
      SELECT h.* FROM fund_holdings h
      JOIN latest l ON l.code = h.code AND l.mp = h.period
    )
    SELECT b.ticker,
           MAX(s.title) AS name,
           COUNT(DISTINCT b.code) AS n_funds,
           AVG(b.weight_pct) AS avg_weight
    FROM book b
    JOIN stocks s ON s.ticker = b.ticker       -- real BIST equities only
    GROUP BY b.ticker
    HAVING COUNT(DISTINCT b.code) >= 2
    ORDER BY COUNT(DISTINCT b.code) DESC, MAX(b.weight_pct) DESC NULLS LAST
    LIMIT ${limit}`;
  return rows.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    n_funds: Number(r.n_funds),
    avg_weight: Number(r.avg_weight),
  }));
}
