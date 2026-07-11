# Research Note 4 — The TEFAS NAV timing lag

**The finding that made every other number honest.**

**Problem.** Our first factor model produced nonsense: a BIST30 *index
fund* showed β = 0.12 against BIST100 with R² near zero, and a pure
Nasdaq fund showed R² = 0.003. Instead of accepting weak results, we
tested lead/lag alignment.

## Evidence

**YEF (Yapı Kredi BIST30 index fund) daily returns vs BIST100:**

| Benchmark lag | corr | β |
|---|---|---|
| 0 (same day) | 0.12 | 0.12 |
| **+1 day** | **0.98** | **0.995** |
| +2 days | 0.07 | 0.07 |

**AFT (Ak Portföy foreign tech fund) daily returns vs Nasdaq (TRY):**

| Nasdaq lag | corr |
|---|---|
| 0 | 0.12 |
| +1 | 0.28 |
| **+2** | **0.51** |
| +3 | −0.09 |

With 5-day overlapping returns at lag +2: **corr 0.80, β 1.01** —
exactly what a fully invested Nasdaq fund must show.

## Explanation

TEFAS publishes a fund's NAV dated `t` computed from the `t−1` close.
Globally priced assets (US equities, COMEX gold) add one more day
because the US close happens after the Turkish valuation point:

```
domestic assets:  NAV(t) reflects market close(t−1)   → lag +1
global assets:    NAV(t) reflects US close(t−2)       → lag +2
```

## Consequences

1. **Any research correlating TEFAS NAVs with same-day market data is
   structurally broken** — betas biased toward zero, alphas inflated
   by exactly the amount of return the model fails to attribute.
   Before the fix, AFT showed "31% unexplained return"; after the fix,
   0.2%. Apparent alpha was a data artifact.
2. All platform betas lag domestic factors +1 day and global factors
   +2 days, and regress 5-day overlapping compound returns to absorb
   residual misalignment.
3. Event studies on Turkish fund data must shift event windows
   accordingly.

This is the kind of institutional data-plumbing detail that separates
usable research from junior mistakes — and it is invisible until an
index fund refuses to have a beta of 1.
