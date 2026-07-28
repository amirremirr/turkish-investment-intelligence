# Product Roadmap & Release Rhythm

## Operating baseline

Validated on 2026-07-27 at 21:04 UTC:

- The serving database passed all nine health checks.
- Fund prices and benchmarks were current through 2026-07-27.
- The daily pipeline, intraday quotes, health monitor, CI, and CodeQL had
  completed successfully.
- The Vercel production deployment was ready.

This baseline is the release gate for the work below. A feature is not
considered shipped until the post-release serving-health check is green.

## Prioritized backlog

### P0 — Source resilience: Yahoo rate-limit handling

The source-contract canary can be rate-limited by Yahoo Finance on GitHub-hosted
runners even while the serving benchmark data remains current. Make the canary
distinguish rate limiting from schema changes, use bounded backoff/jitter, and
escalate only sustained or data-freshness-affecting outages. Preserve a hard
failure for malformed data, missing tickers, or stale serving benchmarks.

**Done when:** a single Yahoo 429 does not create a false outage, repeated 429s
are visible in the alert, and benchmark freshness still protects users from
stale data.

### P1 — Fee-aware active-value analysis

Add reliable fund fee data and expose a net-of-fee version of closet-indexing
and active-value analysis. Clearly label coverage and date provenance.

**Done when:** every supported fund either has an as-of-date fee or an explicit
"fee unavailable" state, and research views do not imply net performance when
the fee is unknown.

### P1 — Holiday-aware stock coverage

Use the BIST trading calendar for stock-price gap detection, calendar-aware
freshness messages, and backfill scheduling. Do not label exchange holidays as
missing data.

**Done when:** planned BIST closures create no alerts, while an unexpected
trading-day gap remains actionable.

### P2 — Factor-model residual diagnostics

Add normality and heteroskedasticity diagnostics to the factor model, show
their applicability limits, and retain the existing Newey-West treatment for
overlapping returns.

**Done when:** each displayed factor result has an interpretable diagnostic
state rather than an implied universal confidence level.

## Weekly release rhythm

| Cadence | Activity | Exit criterion |
|---|---|---|
| Monday | Review open alerts, dependency PRs, and data-status freshness | No unowned P1/P2 incident |
| Tuesday–Wednesday | Implement one scoped backlog item in a PR | Unit tests and local web checks pass |
| Thursday | Review preview deployment, methodology/data-policy impact, and rollback path | PR checks and preview are green |
| Friday | Merge and verify production | `main` CI/CodeQL, production deployment, and serving health are green |
| Monthly | Review coverage, source limits, snapshots, SLO misses, and backlog ordering | Roadmap priorities refreshed |

## Every-release checklist

1. Confirm the change has a reviewed PR and all required checks pass.
2. Confirm the Vercel preview renders the affected routes.
3. Merge, then verify `main` CI and CodeQL.
4. Confirm the production deployment is ready.
5. Run `python scripts/health_cloud.py` and review the data-status page.
6. Update methodology, data-policy, or incident records when claims or data
   behavior changed.
