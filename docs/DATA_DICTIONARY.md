# Data Dictionary

One SQLite database: `data/funds.db`. Raw tables are append/upsert;
`dash_*` presentation tables are dropped and rebuilt by the nightly
pipeline (`python -m tefaslab daily`).

## Raw tables

### funds
| Column | Type | Description |
|---|---|---|
| code | TEXT PK | TEFAS fund code (e.g. `AFT`) |
| title | TEXT | official fund name (Turkish, uppercase) |
| fund_type | TEXT | TEFAS type: YAT / EMK / BYF / GYF / GSYF |
| category | TEXT | platform classification (10 buckets, see METHODOLOGY §5) |

*Source: TEFAS `fonGnlBlgSiraliGetir` + classifier. Refresh: nightly.*

### prices
| Column | Type | Description |
|---|---|---|
| code, date | TEXT PK | fund code, ISO date |
| price | REAL | NAV per share, TRY. **Dated t = computed from t−1 close** (see METHODOLOGY §2) |
| shares | REAL | shares outstanding (`tedPaySayisi`) |
| investors | INTEGER | number of investors (`kisiSayisi`) |
| aum | REAL | portfolio size, TRY (`portfoyBuyukluk`) |

*Source: TEFAS. Refresh: nightly incremental. ~1.06M rows, 2024-01→.*

### allocations
| Column | Type | Description |
|---|---|---|
| code, date, asset | TEXT PK | fund, date, TEFAS asset-class code |
| pct | REAL | portfolio weight, % |

*Source: TEFAS `dagilimSiraliGetirT` (~55 asset codes; legend in
USAGE.md). ~4.5M rows.*

### benchmarks
| Column | Type | Description |
|---|---|---|
| series, date | TEXT PK | series name, ISO date |
| value | REAL | level (index points, TRY rate, or price) |

*Series: bist100, bist30, usdtry, eurtry, gold_usd_oz, nasdaq, sp500,
sector_banks, sector_industrials + derived gold_try_gram, nasdaq_try.
Source: Yahoo Finance. `cpi`/`policy_rate` reserved for TCMB EVDS.*

### stocks
| Column | Type | Description |
|---|---|---|
| ticker | TEXT PK | BIST code (e.g. `THYAO`) |
| title | TEXT | company name (from KAP registry) |
| city | TEXT | HQ city (KAP) |
| sector / industry | TEXT | Yahoo classification (one-time fetch) |

*~776 listings; ~160 are bond issuers/leasing cos with no traded equity.*

### stock_prices
| Column | Type | Description |
|---|---|---|
| ticker, date | TEXT PK | |
| open/high/low/close | REAL | **split/dividend-adjusted** (Yahoo auto_adjust) |
| volume | REAL | shares traded |

*613 tickers with data, ~362k rows.*

## Presentation tables (rebuilt nightly, never edited)

| Table | Purpose | Built from |
|---|---|---|
| dash_metrics | per-fund returns/risk/beta/excess + meta | prices, benchmarks, funds |
| dash_betas | 4-factor betas, alpha, **alpha t-stat**, R² per fund | prices, benchmarks |
| dash_quality | Manager Skill + Investor Suitability scores | metrics, betas, flows |
| dash_cat_flows | 30-day net flow per category | prices (Δshares×NAV), funds |
| dash_rotation | month-end AUM share per category | prices, funds |
| dash_closet_summary / _detail | closet-index classification | betas |
| dash_sectors | 1d/1w/1m median stock return per sector | stock_prices, stocks |
| dash_movers | gainers/losers/turnover/unusual volume boards | stock_prices |
| system_status | key→JSON: pipeline timings, freshness, row counts, breadth, risk appetite, snapshot | pipeline |

## Conventions

- Dates are ISO `YYYY-MM-DD` strings; SQLite has no date type.
- All money amounts are nominal TRY (no inflation adjustment).
- Nothing is forward-filled in raw tables; gaps mean "not reported".
- Deleted/merged funds are **retained** with their historical rows; a
  fund is "dead" operationally when its max(date) trails the universe.
