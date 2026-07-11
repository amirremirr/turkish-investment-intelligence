# Methodology

Every metric in the platform is documented here: definition,
assumptions, and known limitations. Rule-based outputs (memos, reports)
only ever state numbers that trace back to these definitions.

## 1. Returns and risk metrics

- Daily return: `r_t = NAV_t / NAV_{t-1} − 1`, computed per fund with
  missing days left missing (no forward-fill).
- Trailing returns: price ratio over 21/63/126/252 observations
  (1m/3m/6m/1y).
- Annualization: 252 trading days.
- Volatility: `std(daily) × √252`.
- Sharpe: `(mean(daily) − rf/252) / std(daily) × √252`. The risk-free
  rate is an explicit parameter (presentation tables use 40% annual,
  recorded in `system_status`); in a high-inflation market Sharpe is
  meaningless without it.
- Sortino: same numerator over downside-only standard deviation.
- Max drawdown: `min(NAV / cummax(NAV) − 1)` over the full sample.

## 2. NAV timing lag (critical)

TEFAS publishes a fund's NAV dated `t` computed from the `t−1` close;
globally priced assets add one more day (US close is after the Turkish
close). Empirically verified:

| Test | Same-day | Lagged |
|---|---|---|
| BIST30 index fund vs BIST100 | corr 0.12 | **corr 0.98, β 0.995 at lag +1** |
| Foreign tech fund vs Nasdaq(TRY) | corr 0.13 | **corr 0.80, β 1.01 at lag +2 (5-day overlapping)** |

**Consequently: all betas lag domestic factors +1 day and global
factors +2 days.** Any analysis correlating TEFAS NAVs with same-day
market data is structurally wrong. See
[research/04-nav-timing-lag.md](research/04-nav-timing-lag.md).

## 3. Factor model

Per fund, OLS on **5-day overlapping compound returns** (absorbs
residual timing noise):

```
r_fund = α + β₁·r_BIST100(+1) + β₂·r_gold_TRY(+2)
           + β₃·r_USDTRY(+2) + β₄·r_Nasdaq_TRY(+2) + ε
```

- Gold and Nasdaq are converted to TRY before regression, so the
  USDTRY beta captures currency exposure *beyond* what already flows
  through TRY-priced foreign assets.
- α is de-compounded from the K-day intercept and annualized.
- Attribution: `contribution_i = β_i × factor_total_return_i`;
  the residual is labeled **unexplained return** — it bundles missing
  factors, timing, model error, fees, *and* skill. It is deliberately
  not called alpha; separating true alpha requires holdings data.
- Overlapping observations induce autocorrelation: point estimates are
  consistent, but naive standard errors are understated. R² is always
  reported alongside betas.
- **Alpha t-statistic**: OLS standard errors with the residual variance
  inflated by ~K (a crude Hansen–Hodrick-style correction for the
  overlap) — deliberately conservative. Rankings use the t-statistic,
  never raw alpha (32% of funds clear |t| > 2 on the current sample).

## 4. Fund flows

TEFAS provides daily shares outstanding, so net flow is computed
directly rather than inferred:

```
flow_t = (shares_t − shares_{t-1}) × NAV_t
```

equivalent to `AUM_t − AUM_{t-1}(1 + r_t)` but immune to valuation
noise. Positive = money entering. Category flows are sums over funds;
flow ratios normalize by AUM.

- **Price choice**: NAV at *t*, so the identity above holds exactly.
- **Restructuring guard**: flow observations where |daily NAV return|
  > 50% are excluded — share consolidations masquerade as flows (the
  audit found one fictitious −₺1.29tn "flow"; see
  [AUDIT.md §2](AUDIT.md)).

## 5. Classification

Funds → 10 categories via SPK title conventions (regex, word-boundary
aware — "ALTINCI" ≠ "ALTIN"), falling back to the latest portfolio
allocation when no title rule matches.

## 6. Scores

Two deliberately separate rankings; both are cross-sectional
percentiles within a quality-filtered universe (default: AUM ≥ ₺100mn,
≥ 500 investors, ≥ 126 observations).

**Manager Skill** — "is the manager good?"

| Weight | Component |
|---|---|
| 35% | factor-model alpha **t-statistic** (risk removed, noise penalized) |
| 25% | consistency (share of positive rolling 63-day windows) |
| 20% | downside (max drawdown) |
| 20% | factor independence (1 − R²) |

Weight sensitivity was audited: ±5–10pp perturbations leave rank
correlation ≥ 0.995 and 15–20 of the top-20 unchanged
([AUDIT.md §4](AUDIT.md)).

**Investor Suitability** — "should a typical investor buy this?"

| Weight | Component |
|---|---|
| 30% | Sharpe |
| 20% | drawdown |
| 20% | AUM stability (inverse weekly flow volatility) |
| 15% | liquidity (investor count) |
| 15% | size (AUM) |

Fee data is not exposed by TEFAS's API; the liquidity/size slots stand
in until an expense-ratio source is added.

## 7. Regression methodology (research studies)

- Univariate OLS with intercept; β, naive t, **Newey–West t** (Bartlett
  kernel, lag = overlap length), R², n reported.
- Out-of-sample protocol: estimate on 2024–2025, verify sign and
  magnitude on the 2026 holdout (`research flows-oos`).
- Regime splits use trailing 21-day BIST100 volatility vs its median.
- Flow series are normalized by category AUM (% of AUM per day) and
  restructuring-guarded (§4).
- **Cash-carry caveat**: the factor model has no risk-free factor, so
  the intercept of deposit-like funds is dominated by interest carry —
  100% of money-market funds show "significant alpha" by construction.
  Interpret alpha within category (`quality --within-category`), never
  across cash-like and risky products.

## 8. Macro regime engine

TCMB EVDS series (cpi_index, policy_rate = CBRT average funding cost,
deposit rates) classify the environment with explicit thresholds:

| Dimension | Rule |
|---|---|
| Inflation | HIGH ≥ 40% yoy · ELEVATED 20–40% · MODERATE < 20%; trend from the previous month's yoy |
| Rates | real rate (policy − yoy CPI): RESTRICTIVE > +5pp · NEUTRAL ±5pp · LOOSE < −5pp |
| FX | 3m USDTRY change: STRESS > 8% · DRIFT 2–8% · STABLE < 2% |

"Historical winners" are median monthly category fund returns within
each regime bucket (nominal TRY). **Caveat**: the 2024–26 sample is
almost entirely RESTRICTIVE months — regime comparisons will only
become meaningful as the sample spans an easing cycle. CPI publishes
with ~1 month lag; the real rate uses trailing, not expected,
inflation.

## 9. Known limitations

1. **Sample**: Jan 2024 – present (~2.5 years). Findings are one
   regime's evidence, not universal laws.
2. **Survivorship**: funds that closed remain in the database from
   their live period, but pre-2024 closures are absent.
3. **Small-fund artifacts**: private funds ("özel", often < 30
   investors) show ±800% NAV jumps from restructurings. Quality filters
   exclude them from rankings; raw tables keep them.
4. **No fee data**: closet-index findings identify *index-like
   exposure*, not net-of-fee value destruction, until expense ratios
   are added.
5. **Yahoo stock data**: solid for large caps; small tickers can have
   gaps or odd split adjustments.
6. **Statistical caveats**: overlapping returns (see §3, §7); single
   BIST100 benchmark for excess returns regardless of category.
