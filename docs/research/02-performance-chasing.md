# Research Note 2 - Aggregate performance chasing did not survive a fund-level test

**Status: retired as a behavioural claim.**

An earlier category-aggregate regression found that weekly Equity Turkey
flows were associated with trailing 63-day returns (Newey-West t about 4.3).
That result is not sufficient to claim that individual investors chase fund
winners: it combines a common market/category shock with every fund.

The stricter test is a fund fixed-effects panel of each fund's weekly net flow
(as a percent of AUM) on its own lagged 63-day return, with standard errors
clustered by week. It reduces the statistic to about **t = 1.2**. The result
does not survive as a supported behavioural finding, let alone a trading
signal.

## What remains useful

- The aggregate series is descriptive of category-level allocation changes.
- It can generate a pre-registered question for a future, longer sample.
- It must not be cited as evidence that Turkish fund investors chase winners.

## Research controls

The original work examined multiple lookbacks and aggregate variants. Future
tests must register their horizon, category, model, sample split, and success
criterion before viewing the holdout. Results from exploratory variants are
labelled exploratory and are not promoted to product findings.

*Reproduce the fund-level check:* `python -m tefaslab research panel`.
