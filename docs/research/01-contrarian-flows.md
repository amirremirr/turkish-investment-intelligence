# Research Note 1 — Retail fund flows are mildly contrarian

**Question.** Do aggregate flows into Turkish equity mutual funds
predict subsequent BIST100 returns?

**Data.** Daily net flows for all TEFAS equity funds (Jan 2024 – Jul
2026, ~605 trading days), computed as Δshares × NAV and normalized by
category AUM; forward BIST100 returns at 1/5/10/21-day horizons.

**Method.** `R_{t+1:t+h} = α + β·Flow_t + ε`, Newey–West (Bartlett)
standard errors with lag = horizon. Restructuring rows (|NAV move| >
50%) excluded from flows (see METHODOLOGY §4).

## Results

| Horizon (days) | β | naive t | **NW t** | R² |
|---|---|---|---|---|
| 1 | −0.22 | −1.9 | −2.2 | 0.006 |
| 5 | −0.26 | −0.9 | −1.1 | 0.001 |
| 10 | −0.56 | −1.5 | −1.7 | 0.004 |
| 21 | **−1.11** | −2.0 | **−2.5** | 0.007 |

β is negative at every horizon: a 1%-of-AUM inflow into equity funds is
associated with ~1.1pp *lower* BIST100 returns over the following
month. Explained variance is small (<1%) — a behavioral tilt, not a
trading signal.

**Out-of-sample** (train 2024–2025, test 2026):

| Sample | β (21d) | NW t | n |
|---|---|---|---|
| Train (2024–25) | −1.09 | −2.3 | 498 |
| Test (2026) | −1.29 | −0.9 | 108 |

The holdout shows the same sign and comparable magnitude; the test
t-statistic is weak, as expected from ~5 months of data — sign
consistency is the claim, not holdout significance.

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
