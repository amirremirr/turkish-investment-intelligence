# Signal Lab: research-to-decision-support architecture

## Purpose

Signal Lab turns repeatable market observations into transparent decision
support. It is **not** an execution engine, personalized investment advice, or
a promise of return. A signal can progress only through explicit research
states; the product must never make an exploratory rule look validated.

The initial use case is BIST momentum exhaustion: crowded prior-day moves that
open sharply higher may be poor entries at the next open. The companion
long-side hypothesis, quiet momentum, remains paper-trade research only.

## Product states

| State | Meaning | User-facing language | Automation allowed |
|---|---|---|---|
| `research` | Hypothesis or historical observation | “Exploratory pattern” | Research artifact only |
| `paper` | Frozen rule logging prospective outcomes | “Paper-tracked candidate” | Watchlist / ledger |
| `validated` | Passes declared prospective gates | “Decision-support candidate” | Ranked context, never auto-execution |
| `retired` | Fails or becomes unstable | “Retired hypothesis” | Historical record only |

No state emits an unconditional “buy” or “sell.” The public vocabulary is:

- **Candidate** — a paper or validated long-side setup with horizon and risk
  conditions.
- **Avoid chase** — an exhaustion warning for a new entry.
- **Exit review** — risk context for an existing holding; not an instruction to
  sell.
- **Ineligible / uncertain** — missing liquidity, stale data, price limit,
  suspension, or unavailable execution information.

## Signal objects

Every generated observation is immutable and versioned.

```text
signal_id             UUID
signal_version        e.g. exhaustion-v1
as_of_timestamp       when the decision information became available
ticker
state                 research | paper | validated | retired
classification        candidate | avoid_chase | exit_review | uncertain
features_json         raw, unrounded inputs and thresholds
source_quality        official_close | delayed_open | intraday_bar | order_book
entry_rule            declared, never inferred after the fact
exit_rule             declared, never inferred after the fact
data_cutoff           latest source timestamp used
created_at
```

`signal_version` changes whenever a threshold, input, timing convention, cost
model, or outcome definition changes. Results are never pooled across versions.

## Initial scorecards

### Exhaustion watch — `research`, visible as risk context

Flag only when all of the following are observed:

1. prior-day return at least 7%;
2. prior-day turnover at least 2x its prior-20-session median;
3. provider-reported next-session opening gap at least 1%.

Prior five-session return of at least 15% and two or more prior positive days
increase the severity, but do not create a trade recommendation. A daily open
is a source-provided price field, not proof of auction fill or available size.

### Quiet momentum — `paper`, not public as a buy signal

The first frozen prospective specification is intentionally narrow:

1. prior-day return 7–9%;
2. turnover shock 0.5–1.0x;
3. prior-20-session median trading value at least TRY 10m;
4. close-strength at least 0.60;
5. no more than one prior positive session.

The historical robust test did not support this rule. It remains in the ledger
only to measure whether future, genuinely untouched observations differ.

## Data architecture

```text
Official daily OHLCV ─┐
Delayed current open ─┼─> feature engine ─> immutable signal ledger
Intraday 1/5m bars ──┤                         │
Auction/order book ──┤                         ├─> paper portfolio ledger
KAP catalysts ───────┘                         └─> public decision-support UI
```

### Required source-quality tiers

| Tier | Data | What it can support |
|---|---|---|
| 0 | Daily OHLCV | Historical close-to-open/open-to-close description |
| 1 | Delayed daily open | Live exhaustion watch only, with source caveat |
| 2 | 1- or 5-minute bars | Entry timing, VWAP, adverse excursion, intraday exits |
| 3 | Auction and order-book fields | Fill probability, capacity, price-limit queue risk |
| 4 | Dated KAP/catalyst mapping | Information-versus-crowding research |

Any signal requiring a higher tier must render as `uncertain` when that tier is
unavailable. Do not substitute a later quote for an opening-auction value.

## Paper-trade ledger

The paper ledger records every eligible signal—not only attractive outcomes.

```text
paper_trade_id, signal_id, ticker, entry_timestamp, intended_entry,
observed_entry, exit_timestamp, observed_exit, gross_return, costs_bps,
net_return, max_adverse_excursion, max_favourable_excursion,
rejection_reason, source_quality, recorded_at
```

For an open-based rule, store both the observed opening price and the first
tradable intraday price once Tier 2 is available. This keeps execution
assumptions visible rather than silently granting an impossible fill.

## Promotion gates

A paper signal can be considered for `validated` only after a pre-declared
prospective sample across materially different market conditions. Minimum gates
are:

1. positive **net** mean and median after a conservative cost model;
2. positive results after excluding the best 1%, 5%, and 10% of observations;
3. acceptable drawdown, losing streak, capacity, and missing-data rate;
4. stability by liquidity bucket, sector, volatility regime, and calendar
   period;
5. no selective exclusion of price-limit, suspension, or unavailable-fill
   events;
6. review of multiple testing across all signal versions and variants.

The exact sample threshold is set before the paper period begins. If a rule
fails any gate, it becomes `retired`; it is not retuned on the same paper data.

## User experience

### Market page

- **Exhaustion watch**: red, experimental risk context; show raw inputs,
  source time, and “avoid chasing” language.
- **Signal Lab status**: number of paper observations, coverage, missing-data
  rate, and next scheduled evaluation—not a performance headline.

### Stock page

- Current classification and the exact rule version.
- Explainable drivers: prior-day return, turnover shock, prior run-up, opening
  gap, source quality, and unavailable inputs.
- A link to methodology and paper-trade history. Never show a single composite
  score without its inputs.

### Research page

- Versioned results, pre-registration date, full scenario family, costs,
  holdout status, and retired hypotheses.

## Delivery sequence

1. **Now** — experimental exhaustion watch; complete.
2. **Next** — create immutable signal and paper-trade tables; begin prospective
   quiet-momentum and exhaustion records without public long/short calls.
3. **Data upgrade** — ingest and retain 1/5-minute bars plus opening-auction
   data; add execution-quality fields.
4. **Intraday research** — test gap path, VWAP entry, time stops, and adverse
   excursion using frozen rules.
5. **Validation review** — apply promotion gates and either validate or retire
   each version.
6. **Decision support** — expose only validated candidates, still with risk,
   horizon, cost, and uncertainty information.

## Non-goals

- Brokerage integration or automatic order submission.
- Personalised portfolio advice.
- A public short recommendation without symbol-level borrow, market-rule, and
  execution verification.
- Machine-learning optimisation before a sufficiently large prospective,
  point-in-time dataset exists.
