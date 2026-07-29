# Daily attention--momentum study

Status: **exploratory**. This is a historical test of a stated rule, not a
recommendation, forecast, or a claim that an order could have been filled.

## Question

Do BIST shares showing fresh, liquid, end-of-day buying attention at close
`t` earn a small positive **executable** return from the next session's open
to close? The competing explanation is exhaustion/reversal: a large daily
move may already have incorporated the attention before an investor can act.

The primary economic threshold is the return after round-trip trading costs,
not merely whether the gross average is above zero.

## Data and timing

- Source: locally stored Yahoo daily BIST OHLCV, sourced through
  `tefaslab.stocks`.
- Unit of observation: an equal-weighted daily portfolio. Selected shares on
  the same day are not treated as independent observations.
- Signal: calculated after the official close on day `t`.
- Primary execution: enter at recorded **open on t+1**, exit at recorded
  **close on t+1**. If either price is missing, that selected share is not
  treated as executed.
- Diagnostics: close-to-next-open (theoretical, not assumed tradable),
  close-to-next-close, and open-to-close horizons of 1, 2, 3, 5, 10 and 21
  sessions.
- Benchmark: equal-weighted same-session open-to-close return of the eligible
  universe. It is reported only for the one-session executable outcome.

Daily bars do **not** support tests of first-30-minute exits, closing-auction
queue position, order-book fill probability, actual spread, or news timing.
Those scenarios are deliberately absent rather than backfilled with a
fictional proxy.

## Pre-specified primary rule

At close `t`, a share is eligible only when it has at least 60 prior observed
sessions, valid OHLCV, and a prior-20-session median trading value of at least
TRY 1m. The trading-value calculation uses only `t-20` through `t-1`.

The primary attention rule selects up to 10 eligible shares satisfying:

1. same-day return percentile at least 90;
2. same-day return from 2% to 9%, avoiding the most obvious limit-up/exhaustion
   cases;
3. trading-value shock at least 2x the prior-20-session median;
4. close location in the day's range at least 0.75; and
5. no more than three consecutive positive days immediately before `t`.

It ranks qualifying shares by:

```
0.35 * return percentile
+ 0.30 * turnover-shock percentile
+ 0.20 * close-strength percentile
+ 0.15 * market-relative-return percentile
```

All percentiles are cross-sectional within the date and eligible universe.
The fixed weights are assumptions, not fitted coefficients.

## Scenario family

Every run reports the complete family below; a favourable row is never
promoted while hiding the other rows.

| Scenario | Purpose |
|---|---|
| `attention_top10` | Primary rule, equal-weighted top 10. |
| `attention_top5` | Concentration sensitivity. |
| `attention_top20` | Diversification sensitivity. |
| `high_turnover_top10` | Requires at least 4x normal trading value. |
| `return_only_top10` | Control: daily winners without attention confirmation. |
| `extreme_winners_top10` | High-return comparison group; may be exhausted/non-executable. |

The output also contains a descriptive matrix by day-`t` return bucket and
turnover-shock bucket. It is hypothesis generation, not a separately
validated strategy.

## Evaluation and inference

For each scenario, execution outcome, cost assumption and sample, the study
reports observations, selected/executed names, mean and median net return,
standard deviation, win rate, equal-weight market abnormal return, worst 5%
mean, skew, maximum drawdown, longest losing streak and positive-month rate.

- Costs: 0, 25, 50 and 100 bps **round trip**; this is a sensitivity range,
  not a claim about realised commission, tax, spread or slippage.
- Inference: Newey--West mean standard errors with lag at least the holding
  horizon, plus a deterministic moving-block bootstrap 95% interval.
- Multiple testing: one-sided Newey--West p-values are adjusted using
  Benjamini--Hochberg FDR across the gross-return scenario/outcome/sample
  family. Cost rows are deterministic sensitivity transformations of the same
  gross return, so assigning them separate p-values would create spurious
  significance merely by subtracting a fixed cost.
- Split: by default, observations before 2026-01-01 are discovery and later
  observations are validation. Rules must not be changed after inspecting the
  validation portion; a later untouched holdout is required for a stronger
  claim.

## Assumptions and known limits

1. Yahoo's daily bars are sufficiently accurate for exploratory aggregate
   research; individual anomalies, gaps and adjusted-price issues remain
   possible.
2. A recorded next open is a pricing proxy, not proof that a portfolio could
   enter at that price. Limit-up, suspension, opening-auction imbalance and
   spread constraints can make the result non-executable.
3. The current ticker history excludes delisted/pre-coverage shares, creating
   survivorship bias. Results must not be described as a complete historical
   BIST universe.
4. Trading value is a liquidity proxy, not capacity. No order may be assumed
   smaller than a fixed share of actual daily turnover until capacity testing
   is added.
5. Sector, market-cap, KAP-news and intraday-path splits require better dated
   metadata or intraday/event data. They are not inferred from daily OHLCV.
6. A positive mean is insufficient. The primary practical question is whether
   the validation-sample median, win rate, drawdown and net return remain
   credible after the cost sensitivity.

## Reproduction

```bash
python -m tefaslab research attention --save reports/attention-momentum
```

Optional `--start`, `--end`, `--split`, and `--min-turnover` arguments change
the declared sample/configuration and therefore create a different research
run. The command writes a Markdown summary, full scenario table, selected
events and the attention matrix.

## Follow-up diagnostics supported by the current data

The study also reports descriptive—not separately validated—daily-bar splits:

- **Opening-gap conditioning.** Primary selections are grouped by their next
  session's close-to-open gap (negative, 0–0.5%, 0.5–1%, 1–2%, and over 2%) and
  their subsequent open-to-close return. This helps identify gap exhaustion,
  but the gap is known only at the open; it is not a pre-open entry rule.
- **Fresh versus exhausted attention.** The primary selection is split by the
  number of positive sessions before the signal and the return over the five
  sessions ending before the signal. `fresh` means no more than one prior up
  day and no more than 5% pre-signal five-session appreciation; `exhausted`
  means at least two prior up days or more than 5% appreciation. The remaining
  names are labelled intermediate.
- **Component quintiles.** Same-day return, turnover shock, close strength,
  relative return, prior five- and twenty-session returns, and prior positive
  streak are each sorted cross-sectionally. These sorts reveal what the fixed
  score is combining before any revised score is considered.
- **Long-horizon stability.** Gross primary results for every open-to-close
  horizon are retained separately for discovery, validation, and full samples.
  The horizons overlap, so Newey--West and block-bootstrap diagnostics remain
  essential and a favourable individual horizon is exploratory.

## Explicitly deferred tests

The current daily OHLCV data cannot answer whether a pre-close signal is
executable in the closing auction, whether last-30-minute or last-15-minute
VWAP predicts the next open, whether an opening reversal occurs in the first
15/30/60 minutes, or whether a stock was locked at its limit with saleable
liquidity. Those require timestamped intraday trades/bars and, ideally,
auction/order-book fields.

Similarly, a KAP-catalyst study must first build a versioned, dated mapping
from disclosures and attachments to issuer tickers. It must not use a generic
fund-notice scrape as a proxy for stock-specific news. Until those inputs are
available, close-to-next-open is only a theoretical diagnostic—not evidence
that “attention matters overnight.”
