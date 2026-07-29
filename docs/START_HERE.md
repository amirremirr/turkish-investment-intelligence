# Start here: what this project does

This project helps people explore Turkish investment funds and listed shares
using public market data. It is designed to answer practical questions such as:

- What does a fund own, when that information is available?
- How has a fund behaved compared with the risks it took?
- Is a fund acting much like an index fund?
- Where are fund investors moving money?
- What has the research tested, and what did it **not** prove?

It is a research and comparison tool. It is **not** a trading service, a
personalised recommendation engine, or a promise that an investment will rise
or fall.

## The short version

| Area | What is available today | Important boundary |
|---|---|---|
| Funds | Daily TEFAS NAV, size, investor-count and allocation data for the observed universe | It is not a full history of every Turkish fund ever created. |
| Shares | Daily BIST price and volume history, plus delayed intraday monitoring | Free market data can have gaps, delays and corporate-action adjustments. |
| Fund holdings | Monthly, stock-level positions recovered from KAP reports where a report can be found and parsed | It is a monthly snapshot, not a live portfolio; coverage is still being built. |
| Fund analytics | Returns, drawdowns, factor exposures, flows and index-likeness comparisons | These are backward-looking calculations, not forecasts. |
| Signal research | Honest tests of possible short-horizon stock patterns, with prospective data collection now underway | There is no validated buy, sell or short signal. |

## What we have learned so far

The useful results are often about avoiding mistakes rather than finding a
magic trade:

1. **Fund NAV dates need careful alignment.** A TEFAS NAV date can reflect
   market information from the previous session. Comparing it mechanically
   with the same day's market move can create misleading beta or alpha.
2. **Some funds look very similar to their benchmark.** The platform can flag
   index-like exposure; this describes exposure, not whether a fund is good
   value after fees.
3. **The initial daily stock-attention strategy did not work.** Large,
   high-volume winners were more likely to fade the next day than continue.
   That result is retained, rather than hidden.
4. **A possible early-session pattern needs real intraday evidence.** The
   system is now collecting 5-minute bars prospectively for defined events.
   Until enough future observations exist, it remains a question, not a
   trading rule.

For the full, plain-language result register, see
[Current research results](RESULTS.md).

## How the data becomes a page or result

```
Public sources
TEFAS / KAP / TCMB EVDS / Yahoo Finance
        |
        v
Scheduled collection and validation
        |
        v
Stored data and calculated metrics
        |
        +--> website and Streamlit research terminal
        +--> reproducible reports and research notes
```

The collection jobs run on a schedule and record freshness, coverage and source
errors. A value is not assumed correct simply because a job completed; the
project also checks for missing data, abnormal changes and coverage drops.

## A simple guide to the terminology

| Term | Plain-English meaning |
|---|---|
| **NAV** | The reported value of one unit of a fund. |
| **AUM** | The total money managed by a fund. |
| **Fund flow** | An estimate of money entering or leaving a fund, inferred from changes in its unit count. |
| **Factor exposure / beta** | How strongly a fund historically moved with a market driver such as BIST, FX, gold or US technology shares. |
| **Alpha** | The part left over after a simple model explains known market exposures. It is not automatically manager skill. |
| **Closet indexer** | A supposedly active fund whose historical returns closely resemble an index. |
| **Holdings coverage** | The share of funds or reports for which the project has successfully found and parsed a usable KAP portfolio report. |
| **Exploratory** | An interesting historical pattern that is not confirmed enough to rely on. |
| **Retired** | A claim that was tested more carefully and did not hold up. It stays documented for transparency. |

## What to read next

Choose the route that matches your question:

- **I want to use the website or local terminal:** [Usage guide](USAGE.md)
- **I want to understand today’s research conclusions:** [Current research
  results](RESULTS.md)
- **I want to know exactly how calculations are made:** [Methodology](METHODOLOGY.md)
- **I want to know what data exists, how current it is, and where gaps are:**
  [Data policy](DATA_POLICY.md), [data dictionary](DATA_DICTIONARY.md), and
  [KAP holdings status](KAP_HOLDINGS.md)
- **I want the detailed studies and code-reproduction commands:** [Research
  notes](research/README.md)
- **I want to understand the operating system and controls:**
  [Architecture](ARCHITECTURE.md), [monitoring](MONITORING.md), and
  [operations](OPERATIONS.md)

## What this project deliberately does not claim

- It does not know every fund's current holdings every day.
- It does not include a complete dated fee history, so it cannot claim that a
  fund's gross model result is an investor's net return.
- It does not have a validated predictive stock-trading signal.
- It does not give personal investment advice.
- It does not treat missing data as zero or unknown data as a negative result.

Those limits are part of the product, not small print. They help keep a useful
research tool from sounding more certain than its data allows.
