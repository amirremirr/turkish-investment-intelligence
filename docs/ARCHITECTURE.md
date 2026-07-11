# Architecture

The platform follows a warehouse (ETL) design: **the dashboard never
computes — it only visualizes**. All analytics are transformed into
presentation tables by a scheduled nightly pipeline.

```
┌────────────┐  ┌────────────┐  ┌─────────────┐
│   TEFAS    │  │    KAP     │  │    Yahoo    │
│ fund NAVs, │  │  company   │  │ BIST stocks,│
│ AUM, alloc │  │  registry  │  │ FX, indices │
└─────┬──────┘  └─────┬──────┘  └──────┬──────┘
      └───────────────┼────────────────┘
                      ▼
              ETL  (tefaslab daily)
        scheduled weekdays 18:30, logged,
        1 retry, failure notification
                      │
                      ▼
        ┌─────────────────────────────┐
        │      RAW TABLES (SQLite)    │
        │ prices · allocations ·      │
        │ stocks · stock_prices ·     │
        │ benchmarks · funds          │
        └──────────────┬──────────────┘
                       ▼
              ANALYTICS ENGINE
        metrics · factor models · flows ·
        quality scores · classification ·
        market intelligence · research
                       │
                       ▼
        ┌─────────────────────────────┐
        │   PRESENTATION TABLES       │
        │ dash_metrics · dash_quality │
        │ dash_betas · dash_cat_flows │
        │ dash_rotation · dash_closet │
        │ dash_sectors · dash_movers  │
        │ system_status (freshness)   │
        └──────┬──────────┬───────────┘
               ▼          ▼
        DASHBOARD      PRODUCTS
        (Streamlit     monthly report ·
        multipage,     investment memos ·
        SELECT * only) research studies
```

## Layers

| Layer | Contents | Rebuilt |
|---|---|---|
| Raw | 1.06M fund-price rows, 4.5M allocation rows, 362k stock OHLCV rows, 17 benchmark series | incrementally, nightly |
| Derived / presentation | 10 `dash_*` tables + `system_status` | fully, nightly (~1 min) |
| Views | 8 Streamlit pages ([views/](../views)) | never — pure `SELECT *` |

## Design decisions

- **SQLite, one file** (`data/funds.db`). Adequate for a single-writer
  analytical workload at this scale; layering is expressed in the
  schema (`dash_*` prefix), which maps directly onto Postgres schemas
  when a multi-user deployment justifies migration.
- **Multipage dashboard** (`st.navigation`): only the active page
  executes. Instant pages read presentation tables (~0.1 s); the only
  live computation is per-fund on-demand work and the Research Lab,
  where users explicitly press *Run*.
- **Everything is upserted**, so any backfill or pipeline run is safely
  resumable and re-runnable.
- **`system_status`** records per-step timings, row counts, and
  freshness. The dashboard surfaces failure/staleness banners; the
  Developer page exposes the full status.

## Operations

- `python -m tefaslab daily` — full ETL (raw refresh + rebuild + health
  checks); `--skip-raw` for analytics-only rebuild.
- Windows Task Scheduler runs [scripts/run_daily.py](../scripts/run_daily.py)
  weekdays at 18:30: logs to `logs/`, retries once after 10 minutes,
  raises a desktop notification and a dashboard banner on failure.
- `python -m tefaslab health` — 9 data-quality checks (freshness,
  coverage, impossible values, return outliers, month continuity,
  benchmark staleness, classification); non-zero exit for schedulers.

## Data source notes

- **TEFAS** JSON API: max 1-month window per request, row pagination,
  429 rate-limiting handled with backoff. The HTML site is behind an
  F5 anti-bot challenge; the JSON API is not.
- **KAP**: JSON API is bot-protected, but server-rendered pages are
  plain HTML — the company registry and fund metadata are parsed from
  them. The same route supports the planned holdings parser.
- **Yahoo**: `<TICKER>.IS` daily OHLCV for 613 traded stocks; most BIST
  sector indices have no Yahoo history, so sector performance is
  computed from our own stock prices grouped by per-ticker sector tags.
