# Research Note 1 — Retail fund flows are mildly contrarian

**Question.** Do aggregate flows into Turkish equity mutual funds
predict subsequent BIST100 returns?

**Data.** Daily net flows for all TEFAS equity funds (Jan 2024 – Jul
2026, ~605 trading days), computed as Δshares × NAV and normalized by
category AUM; forward BIST100 returns at 1/5/10/21-day horizons.

**Method.** `R_{t+1:t+h} = α + β·Flow_t + ε` (OLS; see
[METHODOLOGY §7](../METHODOLOGY.md#7-regression-methodology-research-studies)
for caveats — overlapping horizons inflate t-statistics).

## Results

| Horizon (days) | β | t | R² |
|---|---|---|---|
| 1 | −0.21 | −1.9 | 0.006 |
| 5 | −0.24 | −0.9 | 0.001 |
| 10 | −0.60 | −1.7 | 0.004 |
| 21 | **−1.08** | **−2.1** | 0.007 |

β is negative at every horizon: a 1%-of-AUM inflow into equity funds is
associated with ~1.1pp *lower* BIST100 returns over the following
month. Explained variance is small (<1%) — a behavioral tilt, not a
trading signal.

## Robustness

**Volatility regimes** (trailing 21d BIST100 vol vs median):

| Subsample | β (10d) | t |
|---|---|---|
| Low-vol (calm markets) | **−1.45** | **−2.3** |
| High-vol (turmoil) | +0.10 | 0.2 |

The effect lives entirely in *calm* markets: investors who buy equity
funds during quiet rallies buy into subsequent weakness. It is a
complacency phenomenon, not panic behavior.

**Category specificity** (21d horizon):

| Flow category | β | t |
|---|---|---|
| Equity Turkey | −1.08 | −2.1 |
| Foreign Equity | −0.03 | −0.2 |
| Precious Metals | +0.50 | 0.9 |
| Money Market | +0.08 | 1.0 |
| Hedge (Serbest) | +0.22 | 0.2 |

Only domestic equity flows carry the signal. "Fund flows" are not one
thing.

## Interpretation & limitations

Consistent with the dumb-money literature: retail allocation follows
comfort, and comfort peaks late. Sample covers a single 2.5-year
regime; t-statistics are modest and horizon overlap inflates them.
Treat as suggestive, not tradable.

*Reproduce:* `python -m tefaslab research flows [--regime low_vol]`,
`python -m tefaslab research flows-by-category`
