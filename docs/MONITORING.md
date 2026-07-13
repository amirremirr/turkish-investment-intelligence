# Monitoring & Alerting

The platform is several moving parts (nightly pipeline, 15-minute
intraday cron, CI, Supabase, the web app, and four external data
sources). This is how a failure — now or in the future — gets caught
and surfaced to you.

## Two layers

**1. Immediate, per-run — GitHub failure emails.**
Every workflow (`daily`, `intraday`, `ci`, `monitor`) reports success or
failure. GitHub emails the repo owner when a run fails. This catches
loud failures (a code error, a missing dependency, a bad deploy) within
minutes. Each workflow also has a **secret-presence guard** that fails
early with a clear message if `SUPABASE_DB_URL` / `EVDS_API_KEY` are
missing, and the daily pipeline **retries once** on transient errors
before giving up.

> Enable it: GitHub → your avatar → Settings → Notifications →
> **Actions** → check "Send notifications for failed workflows only".

**2. Daily, whole-system — the health monitor.**
[`monitor.yml`](../.github/workflows/monitor.yml) runs
[`scripts/health_cloud.py`](../scripts/health_cloud.py) every day at
06:00 UTC (and on demand). It connects to Supabase and verifies the
**data**, not just that jobs ran — so it catches *silent* failures too
(a cron that stopped, a partial publish, stale data). On any hard
failure it **opens a GitHub Issue** (which notifies you) and fails the
run (which emails you). One issue per outage; repeat failures comment
on it instead of spamming.

## What the monitor checks

| Check | Hard-fails if | Catches |
|---|---|---|
| Supabase connection | can't connect | DB down / bad credentials |
| Pipeline failure flag | last run flagged failure | nightly pipeline errored |
| Fund price freshness | latest price > 6 days old | ingestion stopped |
| Row-count sanity | funds < 2k, prices < 1M, etc. | truncated / partial publish |
| Presentation tables | < 8 `dash_*` tables | analytics build broke |
| Pipeline recency | (warn) > 40h since last completion | nightly not running |
| Benchmark freshness | (warn) > 7 days | market-data feed stalled |
| Intraday | (info) last update time | intraday cron health |

Run it yourself anytime: `python scripts/health_cloud.py`
(reads `SUPABASE_DB_URL` from env or `.env`; exit code 1 = a hard
failure). The local Streamlit dashboard's `health` command and the
Developer page cover the same ground for the local SQLite copy.

## What auto-heals vs. what needs you

- **Transient source hiccups** (TEFAS 429, a Yahoo timeout, an
  intraday miss): self-heal — the pipeline retries, the publisher is
  idempotent, and the next scheduled run recovers. No action needed.
- **A stopped cron, stale data, a code/schema break, an expired
  credential, or an external API changing shape**: the monitor opens an
  issue with the failing check named. That's your signal to look.

## Responding to an alert

1. Open the GitHub Issue (or the failed run from the email).
2. The report names the failing check. Read the run log for the
   traceback.
3. Fix, push; the next scheduled run (or a manual `workflow_dispatch`)
   confirms green. Close the issue.
