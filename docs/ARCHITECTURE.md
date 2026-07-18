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
  checks); `--skip-raw` for analytics-only rebuild. Pure Python, no OS
  dependency.
- **Primary scheduler: GitHub Actions**
  ([.github/workflows/daily.yml](../.github/workflows/daily.yml)),
  weekdays 18:30 Istanbul on ubuntu-latest. The stateful SQLite DB
  (KAP holdings history is forward-only) persists between runs via the
  Actions cache, with a zstd-compressed artifact backup (14-day
  retention) after every run. One-time setup: add the `EVDS_API_KEY`
  repo secret, then run the workflow manually once with
  `mode=bootstrap` (~2h full rebuild in the cloud).
- **GitHub Actions is the sole scheduler.** The local Windows tasks
  were deleted (2026-07-17); [scripts/run_daily.py](../scripts/run_daily.py)
  remains only as the retry/logging wrapper the cloud workflow invokes
  and for *manual* local runs. Do not re-register a local schedule —
  two schedulers means two divergent databases.
- **Intraday layer** (every 15 min during BIST hours): refreshes
  delayed quotes (~15 min lag) into `system_status['intraday']` — live
  snapshot, breadth, movers. Runs in the **cloud** via GitHub Actions
  ([intraday.yml](../.github/workflows/intraday.yml), `tefaslab
  intraday-cloud`) writing straight to Supabase, so the public web app
  shows the live view without anything running on a local machine.
  (`tefaslab intraday` still exists to write the same data to local
  SQLite for the Streamlit dashboard.) Provisional data never touches
  the clean daily tables.
  **Update-frequency ceiling by source**: stocks/FX/indices can go
  15-min; KAP disclosures near-real-time; TEFAS fund NAVs publish once
  per day (the 18:30 run already captures same-day NAVs); EVDS macro is
  daily/weekly/monthly.
- `python -m tefaslab health` — 9 data-quality checks (freshness,
  coverage, impossible values, return outliers, month continuity,
  benchmark staleness, classification); non-zero exit for schedulers.
- CI ([ci.yml](../.github/workflows/ci.yml)): unit tests + import smoke
  on every push, on Linux.
- **Source-contract canary**
  ([source_check.yml](../.github/workflows/source_check.yml) →
  [scripts/source_check.py](../scripts/source_check.py)), twice daily
  (01:00 + 13:00 UTC, the latter ~2.5h before the nightly): probes
  TEFAS/KAP/Yahoo/EVDS with one minimal real request each and drives
  the *same* client fetch paths — so the same contract assertions the
  pipeline relies on fire here first. Reusing the real clients keeps the
  contract defined once; the canary can't drift from what the pipeline
  depends on. Per source: OK / CHANGED (schema moved) / DOWN
  (unreachable after retries) / SKIP (no key); any CHANGED or DOWN opens
  a GitHub issue and fails the run. This catches an upstream schema
  change proactively; the daily health monitor catches downstream
  staleness after the fact — two layers, different failure modes.
- **Durable snapshots & reproducibility**
  ([snapshot.yml](../.github/workflows/snapshot.yml) →
  [scripts/snapshot.py](../scripts/snapshot.py)): the Actions cache is
  fast but evictable, and the forward-only KAP history is irreplaceable.
  Weekly (Sun 04:00 UTC) the DB is `VACUUM INTO`'d to a clean single
  file, integrity-checked (`PRAGMA quick_check`) and floor-guarded
  (refuses to publish a truncated DB), zstd-compressed, and uploaded to
  a **GitHub Release** (`snapshot-YYYY-MM-DD`) with a JSON manifest. The
  manifest freezes a **data hash** (`db_sha256`) and a **code hash**
  (`git_sha`): to cite a finding, reference its snapshot tag and the
  exact data + code are pinned. Keeps the newest 8; older tags pruned.
  *Restore*: `gh release download <tag> --pattern '*.zst'`, then
  `zstd -d funds-snapshot.db.zst -o data/funds.db`. Verify against the
  manifest's `db_sha256` before trusting it.

## The two-surfaces rule (durable)

Streamlit and Next.js coexist by a deliberate sequencing rule, not by
accident — and the rule is what keeps "dual cost" from becoming "dual
product":

1. **Streamlit is the private lab bench** — feature-frozen. It exists
   for interactive research (Research Lab, Data Explorer, SQL box) on
   the local compute DB. New product features do **not** land here.
2. **Next.js is the only surface that grows** — anything user-facing
   (screener filters, fund pages, alerts, auth) is built there.
3. **`dash_*` tables are the contract** between compute and both
   surfaces. Any new feature starts by adding to the contract, never by
   computing inside a UI.

If a future change violates rule 1 (e.g. "add Research Lab v2 to
Streamlit"), that's the signal to port the Research Lab to the web
instead.

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
