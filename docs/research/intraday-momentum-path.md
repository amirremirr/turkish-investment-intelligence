# Intraday anatomy of momentum exhaustion

Status: **prospective data capture**. Daily OHLCV cannot establish a 5-, 15-,
or 30-minute trading edge. The intraday collector therefore records bars only
after a versioned exhaustion observation appears; no historical intraday result
is implied.

## Data contract

For every observation in the fixed prospective cohorts, retain adjusted Yahoo
values on a single price basis. The cohorts are: (1) crowded exhaustion:
previous-day gain at least 7%, turnover at least 2x normal and next-open gap at
least 1%; (2) moderate 4-7% gain with ordinary 0.5-1.0x turnover; and (3)
moderate 7-9% gain with ordinary 0.5-1.0x turnover. The two moderate cohorts
also require at least TRY 10m prior-20-session median turnover, close strength
at least 0.60 and no more than one preceding up day.

Each record retains:

- yesterday's official adjusted close and final adjusted turnover;
- prior-20-session **median trading value**, excluding the event day;
- today’s adjusted daily open, provider/retrieval timestamp, and opening gap;
- 5-minute OHLCV bars available after the observation;
- source (`Yahoo Finance`) and quality (`delayed_daily_open` / adjusted bars).

One ticker can produce at most one `signal_id` per signal date and version.
Repeated intraday refreshes upsert bars under that same ID. Missing/stale data
is a source-quality outcome, never silently replaced with a later quote.

## Frozen first questions

For each cohort, measure:

| Window | Outcome |
|---|---|
| open → 5m | immediate auction correction |
| open → 15m | early continuation/failure |
| open → 30m | initial price discovery |
| open → 60m | morning path |
| open → close | daily benchmark |
| 15m/30m → close | delayed-reversal path |

The 7-9% ordinary-turnover group is included because it had a positive raw
historical mean, but a negative median and negative later sample. It is an
explicit replication attempt, not a positive finding.

For a future positive hypothesis, test only after sufficient observations:

> Yesterday’s moderate attention event, next-day gap below 1%, and price held
> above open/VWAP for the first 5–15 minutes may have a short continuation
> window before later exhaustion.

This is not a current strategy. VWAP, first-pullback recovery, and opening
auction fill assumptions remain unavailable until a source with complete,
timestamped session data is validated.

## Validation discipline

- Use equal-weighted signal-day portfolios, not pooled bars.
- Report median, trimmed/winsorized mean, adverse/favourable excursion, and
  the proportion remaining above the opening price.
- Segment by gap (1–2% / 2%+), turnover (2–4x / 4x+), prior run-up, liquidity,
  and market direction.
- Require prospective observations across months before showing any positive
  entry candidate. A red exhaustion watch remains risk context only.
