# Turkish Investment Intelligence Platform

An end-to-end research platform for the Turkish fund and equity market:
automated data pipeline, analytics engine, precomputed intelligence
terminal, auto-generated reports, and reproducible research studies —
built on public data (TEFAS, KAP, Yahoo).

## Why it exists

Turkey has one of the most data-rich retail fund markets in the world —
daily NAVs, AUM, **investor counts**, and portfolio allocations for
~2,000 mutual funds are public — yet almost all retail tooling stops at
"which fund returned the most?" That question is close to meaningless
in a 40%-inflation economy.

This platform answers the questions professionals ask instead:

- *What risk was taken to earn that return?* (factor models, attribution)
- *Where is investor money actually moving?* (exact share-count flows)
- *Is the manager skilled, or just exposed?* (skill vs suitability scores)
- *Am I paying active fees for an index?* (closet-index detection)

## What's inside

| | |
|---|---|
| **Data** | 1.06M daily fund-price rows (NAV/AUM/investors), 4.5M allocation rows, 613 BIST stocks OHLCV, 17 benchmark series — Jan 2024 → present, refreshed nightly |
| **Pipeline** | scheduled ETL with logging, retry, health checks, failure alerts ([architecture](docs/ARCHITECTURE.md)) |
| **Terminal** | 8-page Streamlit app reading precomputed tables — pages load in ~0.1 s |
| **Products** | auto-generated [monthly intelligence report](reports/), rule-based per-fund investment memos |
| **Research** | reproducible studies with documented [methodology](docs/METHODOLOGY.md) |

```
TEFAS · KAP · Yahoo  →  ETL (nightly, scheduled)  →  raw tables (SQLite)
                     →  analytics engine  →  presentation tables
                     →  dashboard · reports · research
```

## Main findings

1. **[The TEFAS NAV timing lag](docs/research/04-nav-timing-lag.md)** —
   NAVs dated *t* reflect the *t−1* close (+2 days for global assets).
   Correcting it moved a BIST30 index fund's measured beta from 0.12 to
   0.995 — and erased what looked like 31 points of "alpha" on a
   foreign tech fund. Same-day analysis of TEFAS data is structurally
   wrong.
2. **[Retail flows are mildly contrarian](docs/research/01-contrarian-flows.md)** —
   equity-fund inflows predict *lower* BIST returns (t≈−2), but only in
   calm markets and only for domestic equity: a complacency phenomenon.
3. **[Investors chase quarterly winners](docs/research/02-performance-chasing.md)** —
   flows respond to trailing 63-day returns (t≈3.0), not weekly moves.
4. **[31 closet index funds identified](docs/research/03-closet-indexing.md)** —
   of 192 large "active" equity funds, 31 run R²≥0.85 at β≈1 with ≈0
   alpha, including major bank funds at R²>0.95 with *negative* alpha.

## Getting started

```bash
pip install -r requirements.txt
python -m tefaslab ingest --start 2024-01-01   # backfill (~30 min)
python -m tefaslab benchmarks && python -m tefaslab stocks --start 2024-01-01
python -m tefaslab classify && python -m tefaslab daily --skip-raw
streamlit run app.py
```

Full command reference: [docs/USAGE.md](docs/USAGE.md)

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — ETL design, layers, operations
- [Methodology](docs/METHODOLOGY.md) — every metric defined, with limitations
- [Audit](docs/AUDIT.md) — institutional-readiness audit: what was checked, what was found, what was fixed
- [Data dictionary](docs/DATA_DICTIONARY.md) — every table and column
- [Research notes](docs/research/) — the four findings as standalone studies
- [Usage](docs/USAGE.md) — CLI reference and database schema

## Status & roadmap

Active. Done recently: institutional audit (with fixes), EMK pension
funds, Newey–West + out-of-sample robustness, TCMB EVDS regime engine,
and the **KAP holdings pipeline** — monthly stock-level fund holdings
(ticker/ISIN/quantity/value/weight) scanned, parsed and queryable
(`holdings who ASELS`); status, upsides and accepted limitations in
[docs/KAP_HOLDINGS.md](docs/KAP_HOLDINGS.md). History accumulates
forward nightly. Next: active share + crowding analytics on top of
holdings, holdings-based attribution, screener, alerts.

*Not investment advice. Built for research and education.*
