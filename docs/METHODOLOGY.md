# Methodology and research standard

This document distinguishes three things that should never be conflated:

1. **Measured facts** — values directly calculated from stated data.
2. **Model outputs** — estimates that depend on assumptions, benchmarks and
   sample choices.
3. **Research claims** — conclusions promoted beyond a chart or table.

The platform is a public-data research tool, not investment advice. A number
may be useful before it is strong enough to support a claim.

## 1. Research status and claim language

Every research result belongs to one status:

| Status | Meaning | Product treatment |
|---|---|---|
| `measured` | Mechanical calculation with documented inputs. | May be displayed with date and coverage. |
| `descriptive` | Historical pattern without a causal or predictive claim. | May be displayed with explicit scope. |
| `exploratory` | Pattern found while searching across choices. | May appear only with an exploratory label. |
| `validated` | Pre-specified test passes its untouched holdout and claim gate. | May be promoted, with its evidence card. |
| `inconclusive` | Evidence is insufficient for either validation or rejection. | May be shown only as a limitation or open question. |
| `retired` | A stronger test, corrected data, or failed holdout invalidated the claim. | Must not appear as a finding. |

No score, alpha estimate, flow, or regime label is a recommendation. Terms
such as *proven*, *skill*, *best*, *predicts*, *causes*, *buy*, or *suitable*
are prohibited unless a separate approved research and compliance process
permits them.

## 2. Reproducibility unit

A publishable research result must record:

- question and economic rationale;
- universe and inclusion/exclusion rules;
- source, retrieval timestamp, data snapshot hash and code revision;
- outcome, benchmark, factor set, estimator and error treatment;
- full hypothesis family, multiple-testing procedure and threshold;
- train/validation/holdout boundaries fixed before holdout inspection;
- effect size, uncertainty, sample count, practical limitations and status.

Weekly frozen snapshots preserve the database and Git revision used for a
result. A material correction preserves the prior snapshot and marks the
affected claim as corrected or retired; it is never silently rewritten.

## 3. Data availability and universe

Analyses use data only when it would have been available to an observer. Fund
NAVs, shares, AUM and investor counts are daily TEFAS observations; a result
using date `t` must not assume it was tradable intraday at date `t`.

The universe is an observed TEFAS-derived universe, not every historical
Turkish investment vehicle. Funds closed before retained coverage are absent;
types with incomplete ingestion must not be described as a complete market.
KAP holdings are report-dependent and forward-built. Missing holdings or
weights mean *unknown*, not zero.

Source availability, legal posture, coverage and fee limitations are governed
by [DATA_POLICY.md](DATA_POLICY.md). All reported figures should name their
as-of date and coverage.

## 4. Returns and risk metrics

- Daily return: `r_t = NAV_t / NAV_(t-1) - 1`; missing observations remain
  missing and are not forward-filled.
- Trailing returns use 21, 63, 126 and 252 observed trading days.
- Annualisation uses 252 trading days.
- Volatility is `std(daily returns) * sqrt(252)`.
- Sharpe is `(mean(daily return) - rf / 252) / std(daily return) * sqrt(252)`.
  The risk-free assumption is visible because an unqualified Sharpe is not
  meaningful in a high-inflation market.
- Sortino uses the same excess-return numerator and downside deviation.
- Maximum drawdown is `min(NAV / cumulative_max(NAV) - 1)` over the selected
  history.

These are backward-looking summaries, not forecasts. Short or discontinuous
histories must show insufficient coverage rather than a precise-looking score.

## 5. Timing and calendar alignment

TEFAS NAV dated `t` reflects prior market information. The current production
convention uses a +1 trading-day lag for domestic factors and +2 days for
globally priced factors. It is validated against liquid index and foreign
funds and avoids the known same-day mismatch.

This is a common convention, not proof that every fund has the same valuation
cut-off. Foreign holidays, derivatives, illiquid securities and fund-specific
pricing policies can still leave timing error in the residual. New asset types
must pass a benchmark-alignment check before their factor interpretation is
published.

## 6. Factor model and attribution

The current model is a compact exposure model, estimated on five-day
overlapping compound returns:

```
excess_fund_return = intercept
  + beta_bist * excess_BIST100(+1)
  + beta_gold * excess_gold_TRY(+2)
  + beta_fx * excess_USDTRY(+2)
  + beta_nasdaq * excess_Nasdaq_TRY(+2)
  + residual
```

Fund and factor returns are reduced by the daily deposit-rate proxy, and
mechanical daily NAV moves beyond the reset guard are excluded. This prevents
cash carry and obvious restructurings from becoming apparent alpha.

Attribution is `beta_i * factor_return_i`. The remainder is called
**unexplained return**, not manager skill: it can contain missing factors,
fees, timing, valuation rules, holdings differences and model error.

### Diagnostics and limits

The model records R-squared, an overlap-adjusted intercept t-statistic,
Jarque-Bera, Durbin-Watson and Breusch-Pagan LM diagnostics. These are review
signals, not a model-validation certificate. Five-day overlap, time-series
dependence and a short sample weaken textbook p-value interpretations.

The model does not yet include bond-duration/credit, sector, style, liquidity,
participation, derivative, or fund-specific mandate factors. A low R-squared
does not imply skill; it means the current model leaves much unexplained.

No individual fund alpha currently survives Bonferroni or
Benjamini-Hochberg false-discovery-rate control. Therefore the product must
not present any individual intercept as citable manager skill.

## 7. Fund flows

Daily net flow is:

```
flow_t = (shares_t - shares_(t-1)) * NAV_t
```

It is equivalent to the AUM-flow identity under consistent reporting. Rows
with an absolute daily NAV move above 50% are excluded as likely resets or
restructurings.

Flow is a reported share movement, not a verified retail decision. It can
include institutional cash management, share-class movements, corrections,
operational transfers and delayed reporting. Category flow is normalized by
category AUM and must not be described as investor conviction without an
investor-level data source.

## 8. Research and inference protocol

### Exploratory work

Exploration may test multiple horizons, categories, volatility regimes and
specifications, but every output is labelled exploratory. A selected result
is not confirmed merely because its sign repeats in a small later period.

### Claim test

Before viewing a holdout, a claim test specifies:

1. the question and economic mechanism;
2. eligible universe and sample dates;
3. outcome, horizon, benchmark and model;
4. a single primary statistic and practical-materiality threshold;
5. all secondary tests belonging to the same hypothesis family;
6. train, validation and holdout boundaries; and
7. the rule for `validated`, `inconclusive` or `retired` status.

For a family of simultaneous tests, report all tests and control either the
family-wise error rate or false discovery rate. Applying FDR only to a chosen
subset after exploring horizons or categories is not sufficient.

### Errors and reporting

Time-series regressions report coefficient, standard error, Newey-West/HAC
settings, t-statistic, sample count and R-squared. Overlapping-return results
require overlap-aware errors. Panel claims use fund fixed effects where
appropriate and standard errors clustered by the shared time shock.

Every result reports effect size in economically meaningful units. Statistical
significance without practical materiality, transaction-cost feasibility,
capacity and stability is not a usable signal.

## 9. Scores and product outputs

### Research score

The public **Research score** is a category-relative, fixed-weight comparison
aid. It combines model precision, return consistency, drawdown and factor
independence after minimum AUM, investor-count and history filters. It is not
a manager-skill estimate, a forecast, or a buy recommendation.

### Suitability score

The **Suitability score** compares Sharpe, drawdown, AUM stability, investor
count and size within category. It is a generic product characteristic, not a
personal recommendation. Fee history, tax, dealing terms, investor horizon,
portfolio context and risk capacity are outside its inputs.

Weight perturbation robustness is useful but insufficient: scores must also
be monitored for time stability, missing-data sensitivity and category
coverage. Missing components should be disclosed rather than interpreted as
evidence of average quality.

## 10. Macro regimes

The regime engine labels trailing inflation, realised policy-rate-minus-CPI,
three-month FX movement and BIST trend using explicit thresholds. Regime
tables are descriptive summaries of realised nominal returns. They do not
estimate causal regime effects or forecast future category winners.

The sample is dominated by restrictive, high-inflation conditions. Regime
comparisons remain insufficiently powered until materially different cycles
accumulate.

## 11. Current claim register

| Topic | Status | Allowed interpretation |
|---|---|---|
| NAV timing lag | `measured` | A necessary alignment correction for stated liquid-fund tests. |
| Closet-index classification | `descriptive` | Index-like exposure classification, not a fee/value judgement. |
| Equity-flow contrarian pattern | `exploratory` | Small historical association; not tradeable or causal. |
| Performance chasing | `retired` | Aggregate result does not survive the fund-level panel. |
| Individual alpha / manager skill | `inconclusive` | No individual citable result after multiple-testing control. |
| Regime winners | `descriptive` | Small-sample historical summary, not a forecast. |
| Daily stock attention--momentum | `exploratory` | Historical daily-OHLCV test; no trade or fill claim. |

## 12. Required upgrades before stronger claims

1. Dated fee and expense-ratio history for net-of-fee analysis.
2. Bond, credit, sector, style, liquidity, participation and mandate-aware
   benchmarks.
3. Longer history including pre-coverage closures and additional fund types.
4. Fund-specific valuation and market-calendar alignment tests.
5. Pre-registered claim files, immutable holdouts and automated claim-status
   checks in CI.
6. Rolling score-stability, benchmark-sensitivity and missingness reports.

Until these are complete, the appropriate product posture is transparent
comparison and reproducible exploration, not investment selection.
