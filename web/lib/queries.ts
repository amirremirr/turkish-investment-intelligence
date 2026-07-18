import { sql } from "./db";
import { intFmt } from "./format";

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

export type DataSet = {
  name: string;
  coverage: string;
  asOf: string | null;
  note: string;
  served: boolean;
};

// Every surface renders the same whether its data is current, months
// stale, or 3% covered — which is exactly why the numbers can't be
// trusted at a glance. This reports the real state of each dataset so
// staleness and thin coverage are visible rather than implied.
export async function getDataStatus(): Promise<{
  sets: DataSet[];
  pipelineAt: string | null;
}> {
  const one = async <T>(fn: () => Promise<T>, fallback: T): Promise<T> => {
    try {
      return await fn();
    } catch {
      return fallback;
    }
  };

  const prices = await one(async () => {
    const r = await sql`SELECT MAX(date) AS d,
      (SELECT COUNT(DISTINCT code) FROM prices
       WHERE date = (SELECT MAX(date) FROM prices)) AS n FROM prices`;
    return { d: r[0].d as string, n: Number(r[0].n) };
  }, { d: null as unknown as string, n: 0 });

  const stocks = await one(async () => {
    const r = await sql`SELECT MAX(date) AS d,
      (SELECT COUNT(DISTINCT ticker) FROM stock_prices
       WHERE date = (SELECT MAX(date) FROM stock_prices)) AS n
      FROM stock_prices`;
    return { d: r[0].d as string, n: Number(r[0].n) };
  }, { d: null as unknown as string, n: 0 });

  const hold = await one(async () => {
    const r = await sql`SELECT COUNT(DISTINCT code) AS f,
      COUNT(DISTINCT period) AS p, MAX(period) AS mp,
      COUNT(DISTINCT code) FILTER (WHERE weight_pct > 0) AS w
      FROM fund_holdings`;
    return {
      f: Number(r[0].f), p: Number(r[0].p),
      mp: r[0].mp as string, w: Number(r[0].w),
    };
  }, { f: 0, p: 0, mp: "", w: 0 });

  const cpi = await one(async () => {
    const r = await sql`SELECT MAX(date) AS d FROM benchmarks
      WHERE series = 'cpi_index'`;
    return r[0].d as string;
  }, null as string | null);

  const bist = await one(async () => {
    const r = await sql`SELECT MAX(date) AS d FROM benchmarks
      WHERE series = 'bist100'`;
    return r[0].d as string;
  }, null as string | null);

  const allocServed = await one(async () => {
    await sql`SELECT 1 FROM allocations LIMIT 1`;
    return true;
  }, false);

  const pipelineAt = await one(async () => {
    const r = await sql`SELECT updated_at FROM system_status
      WHERE key = 'pipeline_complete'`;
    return (r[0]?.updated_at as string) ?? null;
  }, null as string | null);

  return {
    pipelineAt,
    sets: [
      {
        name: "Fund NAVs, returns & scores",
        coverage: `${intFmt(prices.n)} funds`,
        asOf: prices.d,
        served: prices.n > 0,
        note: "Daily NAVs from TEFAS. NAVs lag the market (+1 day domestic, +2 global) — corrected for in every beta and factor model.",
      },
      {
        name: "Stock prices",
        coverage: `${intFmt(stocks.n)} tickers`,
        asOf: stocks.d,
        served: stocks.n > 0,
        note: "BIST closes via Yahoo. Freshness is judged against the index's own trading calendar, so holidays aren't mistaken for gaps.",
      },
      {
        name: "Fund stock-level holdings (KAP)",
        coverage: `${hold.f} funds · ${hold.w} with weights · ${hold.p} period${hold.p === 1 ? "" : "s"}`,
        asOf: hold.mp || null,
        served: hold.f > 0,
        note: "Parsed from monthly KAP portfolio PDFs. This is the thinnest dataset here: coverage is forward-only and currently a small slice of the ~2,400-fund universe, so most fund pages have no book yet.",
      },
      {
        name: "Asset-class allocations",
        coverage: allocServed ? "published" : "NOT published to the serving DB",
        asOf: null,
        served: allocServed,
        note: "Daily equity/bond/cash/FX weights exist for ~2,400 funds in the warehouse but are not served to this site yet — which is why fund pages show no composition breakdown.",
      },
      {
        name: "Macro (CPI, policy & deposit rates)",
        coverage: "TCMB EVDS",
        asOf: cpi,
        served: !!cpi,
        note: "TÜİK rebased CPI and retired the old series, which kept returning valid-looking but frozen data. Now sourced from the continuing 2003=100 index; the vintage is labelled wherever inflation is shown.",
      },
      {
        name: "Benchmarks (BIST100, gold, FX)",
        coverage: "index & FX series",
        asOf: bist,
        served: !!bist,
        note: "Used as the factor set for betas, alpha and the closet-index screen.",
      },
    ],
  };
}

export type CoveredFund = {
  code: string;
  title: string | null;
  category: string | null;
  positions: number;
  weighted: number;
};

// Which funds actually have a disclosed book. KAP coverage is forward-only
// and still small relative to the ~2.4k fund universe, so without a list
// like this you have to click through dozens of funds to find one.
export async function getCoveredFunds(): Promise<CoveredFund[]> {
  const rows = await sql`
    WITH latest AS (
      SELECT code, MAX(period) AS mp FROM fund_holdings GROUP BY code
    ),
    book AS (
      SELECT h.* FROM fund_holdings h
      JOIN latest l ON l.code = h.code AND l.mp = h.period
    )
    SELECT b.code, f.title, f.category, COUNT(*) AS positions,
           COUNT(*) FILTER (WHERE b.weight_pct > 0) AS weighted
    FROM book b
    LEFT JOIN funds f ON f.code = b.code
    GROUP BY b.code, f.title, f.category
    ORDER BY COUNT(*) FILTER (WHERE b.weight_pct > 0) DESC, COUNT(*) DESC`;
  return rows.map((r) => ({
    code: r.code,
    title: r.title,
    category: r.category,
    positions: Number(r.positions),
    weighted: Number(r.weighted),
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

export type Attribution = {
  ticker: string | null;
  name: string | null;
  weight_pct: number | null;
  stock_ret_pct: number | null;
  contribution_pp: number | null;
};

// Stock-selection attribution: each holding's contribution (weight x its
// return) over the month AFTER the report date. Holdings without a local
// price — foreign equities, bonds — have no return and fall into the
// residual, so callers must show priced-weight coverage alongside this
// or the numbers read as more complete than they are.
export async function getFundAttribution(code: string): Promise<Attribution[]> {
  const c = code.toUpperCase();
  const rows = await sql`
    WITH latest AS (
      SELECT MAX(period) AS mp FROM fund_holdings WHERE code = ${c}
    ),
    win AS (
      SELECT to_char((mp || '-01')::date + interval '1 month',
                     'YYYY-MM-DD') AS m1,
             to_char((mp || '-01')::date + interval '2 month',
                     'YYYY-MM-DD') AS m2,
             to_char((mp || '-01')::date + interval '1 month'
                     - interval '20 days', 'YYYY-MM-DD') AS m1_lo,
             to_char((mp || '-01')::date + interval '2 month'
                     - interval '20 days', 'YYYY-MM-DD') AS m2_lo
      FROM latest
    ),
    b AS (
      SELECT h.ticker, h.name, h.weight_pct
      FROM fund_holdings h, latest
      WHERE h.code = ${c} AND h.period = latest.mp AND h.weight_pct > 0
    ),
    -- Both bounds matter: without a lower bound each DISTINCT ON scans
    -- the whole stock_prices table (~5s over 360k rows), and two of them
    -- per cold render blew the serverless timeout. A ~20-day lookback is
    -- enough to find the last close before each month boundary.
    base AS (
      SELECT DISTINCT ON (s.ticker) s.ticker, s.close
      FROM stock_prices s, win
      WHERE s.date < win.m1 AND s.date >= win.m1_lo
      ORDER BY s.ticker, s.date DESC
    ),
    post AS (
      SELECT DISTINCT ON (s.ticker) s.ticker, s.close
      FROM stock_prices s, win
      WHERE s.date < win.m2 AND s.date >= win.m2_lo
      ORDER BY s.ticker, s.date DESC
    )
    SELECT b.ticker, b.name, b.weight_pct,
           (post.close / base.close - 1) * 100 AS stock_ret_pct,
           b.weight_pct * (post.close / base.close - 1) AS contribution_pp
    FROM b
    LEFT JOIN base ON base.ticker = b.ticker
    LEFT JOIN post ON post.ticker = b.ticker
    WHERE base.close IS NOT NULL AND base.close > 0
    ORDER BY contribution_pp DESC NULLS LAST`;
  return rows.map((r) => ({
    ticker: r.ticker,
    name: r.name,
    weight_pct: n(r.weight_pct),
    stock_ret_pct: n(r.stock_ret_pct),
    contribution_pp: n(r.contribution_pp),
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
