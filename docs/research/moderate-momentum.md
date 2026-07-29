# Moderate momentum without attention crowding

Status: **exploratory post-hoc; prospective holdout required**. This study was
created after the attention-momentum outputs indicated that extreme turnover
and large price moves tend to precede next-session exhaustion. It must not be
described as historical validation or as a trading recommendation.

## Frozen question

Do liquid BIST shares with a 4–9% daily gain and **ordinary**, rather than
abnormal, trading value have a better next-session open-to-close outcome than
the crowded attention group?

The study uses the same daily Yahoo OHLCV source and the same signal timing as
the attention study: all filters are observable after close on day `t`; the
only executable return is buy at the recorded open on `t+1` and sell at the
recorded close on `t+1`.

## Locked scenario family

The legs remain separate and use every qualifying name in an equal-weighted
daily portfolio; there is no fitted top-N ranking.

| Scenario | Day-t return | Turnover shock | Liquidity | Other filters |
|---|---:|---:|---:|---|
| `moderate_4_7_normal_turnover_10m` | 4% to 7% | 0.5x to 1.0x | prior 20-session median at least TRY 10m | close strength at least 0.60; at most one prior up day |
| `moderate_7_9_normal_turnover_10m` | 7% to 9% | 0.5x to 1.0x | prior 20-session median at least TRY 10m | close strength at least 0.60; at most one prior up day |

The return ceiling excludes the most obvious limit-up/queue-risk cases, but
daily OHLCV cannot prove that a selected close or next open was tradeable.

## Required reporting

For every leg and historical segment, report equal-weight daily portfolios,
mean, median, 5% winsorized and trimmed mean, win rate, rates above 25 and 50
bps, and the contribution of the best 1%, 5%, and 10% of daily portfolios.
This reveals whether a positive average is a broad effect or a few outliers.

Newey–West and block-bootstrap outputs are reported, but the configured split
is a descriptive historical segment only: the rule was motivated using already
viewed data. The independent test begins only after this specification is
merged and future sessions accumulate.

## Boundaries

- Cost sensitivity is required; gross results alone are not economically
  meaningful.
- The study does not infer borrow availability, auction fills, spread, or
  capacity from daily bars.
- It is not a rescue of the rejected attention top-10 model. That model remains
  a rejected next-day continuation hypothesis.
- A positive historical result must not be promoted to the product until the
  prospective holdout, data-quality checks, and a realistic execution analysis
  support it.

## Reproduction

```bash
python -m tefaslab research moderate-momentum --save reports/moderate-momentum
```
