# Turkish Investment Intelligence Platform

An open, public-data research platform for Turkish funds and listed shares.
It combines scheduled data collection, reproducible analysis, a Streamlit
research terminal and a public web app.

**Start here:** [plain-English project guide](docs/START_HERE.md) ·
[current research results](docs/RESULTS.md) ·
[technical methodology](docs/METHODOLOGY.md)

The platform is for research and education. It is not investment advice,
personalised portfolio advice, or a promise of future returns.

## What it helps you explore

- Fund NAV, assets under management, investor counts and allocation data from
  the observed TEFAS universe.
- Monthly stock-level fund holdings from available KAP portfolio reports.
- Fund flows, drawdowns, factor exposures and index-like behaviour.
- BIST daily-price research and delayed intraday monitoring.
- Reproducible research questions, including results that failed stronger
  tests.

```
TEFAS / KAP / TCMB EVDS / Yahoo Finance
                |
                v
   scheduled collection + validation checks
                |
                v
      stored data + calculated analytics
                |
      +---------+----------+
      v                    v
web application      Streamlit terminal, reports and research
```

![Market overview](docs/screenshots/market.png)

<p align="center">
  <img src="docs/screenshots/stocks.png" width="49%" />
  <img src="docs/screenshots/intelligence.png" width="49%" />
</p>

## Current research position

The project does not turn a historical chart into a recommendation. It records
what is measured, exploratory, inconclusive and retired.

| Topic | Current position |
|---|---|
| TEFAS NAV timing | **Measured:** a market-date alignment correction is necessary before interpreting beta or alpha. |
| Index-like active funds | **Descriptive:** in one study, 52 of 236 large active-labelled funds closely tracked their benchmark. This is not a fee or value judgement. |
| Fund flows | **Exploratory:** a small historical association is not a tradeable or causal conclusion. |
| “Investors chase winners” | **Retired:** the initial result did not survive a stronger fund-level test. |
| Daily stock-attention continuation | **Rejected for use:** the initial next-day test was negative. There is no live buy, sell or short signal. |
| Early-session stock behaviour | **Data collection in progress:** 5-minute bars are being captured prospectively for a future test. |

Read [Current research results](docs/RESULTS.md) for the plain-language
explanation, figures, assumptions and links to every detailed study.

## Documentation

### For readers and users

- [Start here: a plain-English guide](docs/START_HERE.md) - what exists,
  what the project does and does not claim, plus a terminology guide.
- [Current research results](docs/RESULTS.md) - what worked, failed or still
  needs evidence.
- [KAP holdings status](docs/KAP_HOLDINGS.md) - what monthly holdings data
  means, coverage limitations and recovery status.
- [Usage guide](docs/USAGE.md) - commands for running the terminal and data
  pipeline locally.

### For research and technical review

- [Methodology](docs/METHODOLOGY.md) - calculations, assumptions, hypothesis
  control and claim standards.
- [Research notes](docs/research/README.md) - detailed studies and
  reproducibility commands.
- [Data policy](docs/DATA_POLICY.md) - data sources, coverage, corrections,
  privacy and source-use limits.
- [Data dictionary](docs/DATA_DICTIONARY.md) - stored tables and fields.
- [Signal Lab](docs/SIGNAL_LAB.md) - how a future idea can become tested
  decision-support, without pretending an untested idea is a signal.

### For operations

- [Architecture](docs/ARCHITECTURE.md) - pipeline and serving design.
- [Monitoring](docs/MONITORING.md) - freshness, coverage and source checks.
- [Operations](docs/OPERATIONS.md) - releases, incidents and recovery.
- [Audit](docs/AUDIT.md) and [SWOT](docs/SWOT.md) - known gaps and controls.

## Getting started locally

```bash
pip install -r requirements.txt
python -m tefaslab ingest --start 2024-01-01
python -m tefaslab benchmarks
python -m tefaslab stocks --start 2024-01-01
python -m tefaslab classify
python -m tefaslab daily --skip-raw
streamlit run app.py
```

The complete command reference is in [docs/USAGE.md](docs/USAGE.md).

## Data and research limits

- Sources are public interfaces, not guaranteed feeds. They can change,
  throttle, have gaps or require correction.
- KAP holdings are monthly reports, not live portfolios. Missing data means
  unknown, not zero.
- Dated fee data is not yet available, so gross exposure analysis is not a
  statement about investor net returns.
- The current fund-history and holdings universe are not a complete history of
  every Turkish vehicle.
- Historical price patterns do not establish executable returns, especially
  without order-book, spread and fill data.

See [Data policy](docs/DATA_POLICY.md) and [Methodology](docs/METHODOLOGY.md)
for the full limits and correction policy.
