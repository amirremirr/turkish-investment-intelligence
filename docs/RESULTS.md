# Current research results

**Last reviewed: July 2026.** This page is the plain-English register of what
the project has tested. It separates facts we can measure from ideas that still
need evidence. A result can be useful even when it says "do not rely on this."

## Read the status before the headline

| Status | What it means in everyday language |
|---|---|
| **Measured** | We can calculate it directly from stated data and rules. |
| **Descriptive** | It describes the past; it does not predict the future. |
| **Exploratory** | It is an early finding that may be a coincidence, data-specific, or too small to use. |
| **Inconclusive** | There is not enough reliable evidence for a positive or negative conclusion. |
| **Retired** | A stronger test failed. The original idea must not be presented as a finding. |

## Fund research

### 1. TEFAS NAV timing alignment

**Status: measured**

Fund NAVs should not automatically be compared with the same day's market
return. For the liquid fund checks in this project, the safest convention is a
one-trading-day lag for Turkish market factors and a two-day lag for globally
priced factors. In a liquid BIST index-fund check, correcting the alignment
moved the estimated BIST sensitivity from about **0.12 to 0.995**.

**What this means:** an apparently clever fund result can be a calendar
mistake. The correction makes comparisons more honest; it does not prove that
all funds use the same valuation time.

[Read the detailed study](research/04-nav-timing-lag.md) ·
[Read the calculation rules](METHODOLOGY.md#5-timing-and-calendar-alignment)

### 2. Index-like fund exposure ("closet indexing")

**Status: descriptive**

Among 236 large funds labelled active in the study, 52 had historical returns
that tracked their benchmark closely (high R-squared and beta close to one)
without a positive model intercept.

**What this means:** the measure helps a reader ask whether a fund is behaving
very much like an index. It does **not** say whether that fund is bad, whether
its fees are justified, or what it will do next.

[Read the detailed study](research/03-closet-indexing.md)

### 3. Fund flows and market returns

**Status: exploratory**

The historical tests found a small association in which domestic equity-fund
inflows were followed by lower BIST returns in calmer periods. The effect is
statistically interesting in one specification, but it explains less than 1%
of the variation in returns.

**What this means:** this is not a usable trading signal. Flows can represent
institutional cash management, reporting mechanics or many other things - not
simply retail conviction.

[Read the detailed study](research/01-contrarian-flows.md)

### 4. "Investors chase winning funds"

**Status: retired**

An early aggregate result suggested that investors chased recent winners. A
stronger fund-level test reduced the statistical strength from roughly 4.3 to
about 1.2, which does not support the claim.

**What this means:** the platform does not use this as a conclusion. Keeping
the failed result visible is intentional: it shows that the research process
can reject its own first impression.

[Read the detailed study](research/02-performance-chasing.md)

### 5. Individual fund alpha and manager skill

**Status: inconclusive**

No individual fund alpha currently survives the project’s multiple-testing
checks. The model is also deliberately simple: it does not fully capture
bond, credit, sector, style, liquidity, derivative or mandate effects.

**What this means:** a positive residual in the product is called
"unexplained return," not proven manager skill. It may include fees, timing,
model gaps and valuation differences.

[Read the methodology and limitations](METHODOLOGY.md#6-factor-model-and-attribution)

## Stock and signal research

### 6. Buying high-attention daily winners the next day

**Status: exploratory result rejected for use**

The first daily-bar rule selected liquid BIST shares after a positive day,
unusually high turnover and a strong close. It then measured the next session
from the recorded open to close. The main portfolio had a small negative
average return (about **-0.09% gross**) and about **-0.11%** relative to the
eligible market on the same day. It did not pass the statistical or
cost-feasibility gates.

The worse cases were shares that opened with larger gaps: the open-to-close
outcome became materially more negative as the gap increased.

**What this means:** "big move + high volume" is currently an exhaustion-risk
warning, not a buy signal. Daily bars cannot prove an opening-auction fill,
spread, or a first-30-minute trade.

[Read the full test design](research/attention-momentum.md)

### 7. Moderate, quieter momentum

**Status: exploratory post-hoc result; not a strategy**

After the first rule failed, the project also examined more moderate daily
moves with ordinary turnover. The 4-7% group was negative on average. The
7-9% group had a positive raw mean in one sample, but its median was negative
and a small number of outsized days drove the average; the later sample was
negative. Both legs are now collected prospectively as fixed cohorts alongside
the exhaustion group, so their future outcomes can be compared without
changing the rule again.

**What this means:** this does not rescue the original strategy and is not a
buy rule. The scenarios are frozen for future prospective observation rather
than repeatedly adjusted to fit old data.

[Read the full test design](research/moderate-momentum.md)

### 8. Could there be a short window just after the open?

**Status: data collection in progress; no result yet**

The remaining credible question is narrower: after a defined event, does a
share briefly hold above its opening price during the first 5-60 minutes
before a later reversal? Daily price data cannot answer this. The system now
records 5-minute bars **after** qualifying observations occur, using a
consistent adjusted-price basis and a dated signal ledger.

The future study will compare open-to-5, 15, 30 and 60 minutes, plus the rest
of the day. It will report typical outcomes, bad outcomes and coverage - not
just the best average.

**What this means:** no intraday entry, exit, buy or sell signal is live. The
current market display is an experimental "avoid chasing" risk watch only.

[Read the prospective study design](research/intraday-momentum-path.md) ·
[Read the signal-governance plan](SIGNAL_LAB.md)

## Data results and coverage

| Data area | What the project has | What users should keep in mind |
|---|---|---|
| TEFAS funds | Daily NAV, AUM, investor counts and allocation records for the observed TEFAS universe | Closed funds before retained coverage and some fund types are incomplete. |
| KAP holdings | Parsed monthly portfolio reports where reports are discovered and readable | This is monthly, report-dependent and still backfilling. A missing holding means "unknown," not zero. |
| BIST prices | Daily OHLCV and delayed intraday monitoring through Yahoo Finance | Data can be delayed, rate-limited, missing for some tickers, or affected by corporate-action adjustments. |
| TCMB data | Selected macro series through EVDS | The macro engine needs an API key and is skipped if that source is unavailable. |

The live product should always show its as-of time and coverage. For the full
source rules and legal/operational limits, read the
[data policy](DATA_POLICY.md) and [KAP holdings status](KAP_HOLDINGS.md).

## How a result becomes strong enough to show prominently

A future research claim must do all of the following:

1. State the question and rule before inspecting the independent result.
2. Use only information that would have been known at the time.
3. Save the data snapshot, code version, sample, assumptions and all tests.
4. Test realistic costs, liquidity, drawdowns and bad outcomes - not only the
   average return.
5. Control for trying many variations of the same idea.
6. Pass an untouched future holdout, not just old historical data.

Until then, the appropriate label is exploratory, inconclusive or retired - not
"signal." See the complete [methodology](METHODOLOGY.md).

## Important disclaimer

Nothing on this page is investment advice or a recommendation to buy, sell or
hold an instrument. Historical patterns can disappear, data can be corrected,
and real execution can be worse than recorded prices.
