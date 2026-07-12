# Supabase Migration (v2.0)

*Decision record + runbook. Implemented 2026-07-12.*

## The architecture chosen — and why

```
TEFAS · KAP · EVDS · Yahoo
        ↓  nightly ETL (unchanged)
SQLite  (data/funds.db)          ←  COMPUTE engine: local, fast,
        ↓  analytics (unchanged)     millions of upserts per night
dash_* presentation tables
        ↓  python -m tefaslab publish   (SQLAlchemy)
Supabase PostgreSQL              ←  SERVING copy: REST, auth,
        ↓                            future Next.js frontend
Users / apps / API consumers
```

This deliberately **does not** swap the compute engine to Postgres:

1. **Speed**: the pipeline performs millions of local upserts nightly;
   doing that over the network to a hosted Postgres would multiply the
   pipeline runtime for zero analytical benefit.
2. **Size**: the full SQLite file is ~680 MB, over Supabase's free-tier
   500 MB — a *curated serving set* is the right shape regardless of
   tier. The 6M-row `allocations` table (analytics-only) stays local.
3. **Risk**: the codebase has hundreds of SQLite-dialect statements
   (`INSERT OR REPLACE`, `?` placeholders, `PRAGMA`, `GROUP_CONCAT`,
   SQLite date functions). Rewriting them for dual dialects buys
   nothing while SQLite serves compute well — and the advisor's own
   #1 rule ("keep analytics in Python, presentation precomputed") is
   preserved exactly.

The SQLAlchemy abstraction lives where it earns its keep: the
publisher, which can target any Postgres — or a `sqlite:///` URL,
which is how it's smoke-tested without network.

## What is published

| Mode | Tables |
|---|---|
| Full replace (small) | funds, stocks, benchmarks, fund_holdings, kap_disclosures, system_status, all `dash_*` |
| Incremental append | prices (1.3M rows, by date), stock_prices (by date) |
| Not published | allocations (6M rows, analytics-only), live_quotes (ephemeral) |

Estimated serving footprint: ~150–250 MB — inside the free tier.

## Runbook

1. Create a Supabase project → Settings → Database → copy the
   connection string (URI).
2. Add to the local `.env` (gitignored):
   `SUPABASE_DB_URL=postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres`
   For GitHub Actions, add the same as a repo secret and export it in
   the daily workflow env.
3. First run (creates tables + keys):
   `python -m tefaslab publish --init`  (~5–15 min for the initial
   prices upload)
4. Every subsequent `python -m tefaslab daily` publishes automatically
   at the end of the pipeline (skips silently when the URL is absent).

## What this unlocks next (per the v2.x plan)

- **Supabase REST**: `dash_metrics`, `dash_quality`, `fund_holdings`
  are instantly queryable over PostgREST — enable RLS and expose
  read-only anon access to the serving tables.
- **Auth** (v2.2): watchlists / saved screens / alerts as user-owned
  tables with row-level security — no backend code.
- **Next.js frontend** (v2.1): reads Supabase directly; the Streamlit
  terminal remains the local research cockpit.
- Materialized views: not needed yet — dash_* tables *are* the
  materialization (rebuilt nightly by Python, which keeps analytics
  testable in one language).
