# Usage

```bash
pip install -r requirements.txt
```

## Daily operation

```bash
# Full nightly ETL: refresh raw data + rebuild dash_* tables + health
python -m tefaslab daily              # ~5 min with network
python -m tefaslab daily --skip-raw   # analytics only (~1 min)
# Scheduled: Windows task "BIST-Daily-Pipeline", weekdays 18:30, via
# scripts/run_daily.py (logs to logs/, one retry, toast on failure)

# Dashboard — a pure viewer over the dash_* tables
streamlit run app.py

# Monthly Intelligence Report (markdown, saved to reports/YYYY-MM.md)
python -m tefaslab report

# Data quality checks (exit code 1 on hard failures)
python -m tefaslab health

# Database summary
python -m tefaslab stats
```

## Data collection

```bash
# TEFAS fund backfill / incremental update
python -m tefaslab ingest --start 2024-01-01 --end 2026-07-10
python -m tefaslab update
# Fund types (--type): YAT mutual (default), EMK pension, BYF ETFs,
# GYF real estate, GSYF venture capital

# Benchmarks (BIST100/30, USDTRY, EURTRY, gold, Nasdaq, S&P, sectors)
python -m tefaslab benchmarks --start 2024-01-01

# BIST stocks: registry from KAP + daily OHLCV from Yahoo
python -m tefaslab stocks --start 2024-01-01   # full backfill
python -m tefaslab stocks --update             # incremental
python -m tefaslab stocks --sectors            # one-time sector tags

# Fund classification (title rules + allocation fallback)
python -m tefaslab classify

# TCMB macro (CPI, policy rate, deposits) — needs EVDS_API_KEY in .env
python -m tefaslab evds
python -m tefaslab regime   # current regime + historical winners
```

## Analytics

```bash
# Rank funds — rf is the annual risk-free rate for Sharpe/Sortino
python -m tefaslab top --by sharpe --n 20 --rf 0.40
python -m tefaslab top --by ret_1y --category "Equity Turkey" \
    --min-aum 500 --min-investors 1000 --csv rankings.csv

# Two-score ranking: Manager Skill vs Investor Suitability
python -m tefaslab quality --view skill --category "Equity Turkey"
python -m tefaslab quality --view suitability --min-aum 500

# Factor betas + return attribution
python -m tefaslab factors AFT          # one fund, full attribution
python -m tefaslab factors --n 20 --category "Equity" --csv betas.csv

# Rolling 63-day metrics
python -m tefaslab rolling YEF --rf 0.40 --csv yef_rolling.csv

# Estimated net fund flows (share-count based)
python -m tefaslab flows --days 30 --n 10

# Smart money: category flows, AUM rotation, risk appetite
python -m tefaslab smartmoney --days 30 --months 12

# Side-by-side fund comparison
python -m tefaslab compare MAC AFT YEF --rf 0.40

# Single-fund report / investment memo
python -m tefaslab fund AFT --rf 0.40
python -m tefaslab memo AFT --rf 0.40 --save memos/AFT.md
```

## Research

```bash
python -m tefaslab research flows [--regime high_vol|low_vol]
python -m tefaslab research flows-by-category
python -m tefaslab research chasing
python -m tefaslab research closet --min-aum 500
```

## Database schema

SQLite at `data/funds.db`:

**Raw:** `funds(code, title, fund_type, category)` ·
`prices(code, date, price, shares, investors, aum)` ·
`allocations(code, date, asset, pct)` ·
`benchmarks(series, date, value)` ·
`stocks(ticker, title, city, sector, industry)` ·
`stock_prices(ticker, date, open, high, low, close, volume)`

**Presentation (rebuilt nightly):** `dash_metrics`, `dash_betas`,
`dash_quality`, `dash_cat_flows`, `dash_rotation`,
`dash_closet_summary/detail`, `dash_sectors`, `dash_movers`,
`system_status`.

Common allocation codes: `hs` equity, `yhs` foreign equity, `dt` gov
bond, `ost`/`osks` corporate bonds, `tr` reverse repo, `vm`/`vmtl` term
deposit, `km` precious metals, `kh` participation account, `byf`/`yyf`
ETF/foreign fund, `fb` fund basket, `d` FX, `vint` derivatives.
