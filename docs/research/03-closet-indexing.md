# Research Note 3 — 31 closet index funds in the Turkish equity universe

**Question.** Are "active" Turkish equity funds actually active — or is
part of the market selling index exposure at active fees?

**Data.** All Equity Turkey funds with AUM ≥ ₺500mn (192 funds).
4-factor model betas and R² on 5-day overlapping returns with
publication-lag correction (see
[METHODOLOGY §3](../METHODOLOGY.md#3-factor-model)).

**Classification.**

| Bucket | Rule |
|---|---|
| Closet index | R² ≥ 0.85 **and** 0.85 ≤ β_BIST ≤ 1.15 |
| True active | R² < 0.60 |
| Moderately active | everything else |

## Results

| Bucket | Funds | avg β_BIST | avg R² | avg α (annual) |
|---|---|---|---|---|
| Closet index | **31** | 0.93 | 0.93 | **0.09** |
| Moderately active | 58 | 0.67 | 0.76 | 0.11 |
| True active | 103 | 0.58 | 0.19 | 1.49* |

The closet-index bucket self-validates: it contains the actual BIST30
index funds (as it must), and alongside them several major bank-owned
funds marketed as active — including funds at **R² > 0.95 with
negative alpha**: index exposure minus fees.

\* The true-active average alpha is inflated by small serbest funds
with NAV artifacts; the median and AUM-weighted figures are far lower.
Treat the bucket as "genuinely making decisions," not "generating 149%
alpha."

## Why it matters

For an investor, the question "am I paying active fees for passive
exposure?" is directly answerable from public data. Once expense
ratios are added, the natural extension is an *active value* metric
(`alpha − fees`) identifying funds that systematically destroy value —
the most commercially relevant output this platform can produce.

## Limitations

R² thresholds are conventions, not laws; a factor model with BIST100
only (no size/style factors) can overstate "activeness" for small-cap
tilted funds. No fee data yet. 2.5-year sample.

*Reproduce:* `python -m tefaslab research closet --min-aum 500`
