# Bounded momentum-condition discovery

Status: **historical discovery only**. This study searches a fixed and fully
reported condition family for possible next-session open-to-close candidates.
It does not create a trading signal, even if a row is positive.

## Why this exists

The earlier 7-9% ordinary-turnover result had a positive average but a negative
median and negative later sample. The question is therefore not "how do we
make 7-9% work?" It is whether any simple, interpretable and liquid condition
has enough evidence to deserve prospective observation.

## Fixed search family

The starting universe contains shares with at least 60 prior sessions, a
prior-20-session median trading value of at least TRY 10m, and a positive
prior-day return of at least 2%.

Every row is a prior-day return bucket alone (2-4%, 4-7%, 7-9%, 9%+) or that
same bucket paired with **one** of these observable conditions:

- turnover shock;
- next-session opening gap (known only after the open);
- prior-day close strength;
- return over the preceding five sessions; or
- count of prior positive days.

The study does not fit a ranking, combine arbitrary five-way filters, or hide
unfavourable rows. It uses equal-weighted daily portfolios, rather than
pretending all shares selected on a day are independent experiments.

## Triage rule

Each row uses a 50 bps round-trip cost sensitivity, Newey-West uncertainty and
Benjamini-Hochberg FDR correction across the complete output. A row is marked
only as a **provisional candidate** if it has at least 30 independent portfolio
days, a positive mean and median after that cost, and FDR q <= 0.10.

That is a search filter, not validation. Any survivor must be frozen and tested
on future, untouched sessions before it can be added to the live collector or
presented as evidence.

## Reproduction

```bash
python -m tefaslab research momentum-discovery --save reports/momentum-discovery
```

The GitHub Actions workflow **Bounded momentum discovery** uploads the complete
summary, daily portfolios, events and any provisional-candidate file as an
artifact. A report with no candidates is a valid and informative result.
