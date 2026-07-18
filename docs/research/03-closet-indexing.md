# Research Note 3 — closet indexing in the Turkish equity universe

**Question.** Are "active" Turkish equity funds actually active — or is
part of the market selling index exposure at active fees?

**Data.** All Equity Turkey funds with AUM ≥ ₺500mn (**236 funds** at
the latest rebuild; the universe was 192 when this note was first
written — it grows as funds cross the size threshold). Betas and R² from
the factor model on 5-day overlapping returns with publication-lag
correction (see [METHODOLOGY §3](../METHODOLOGY.md#3-factor-model)).
Alpha is estimated in **excess-of-cash** terms (the risk-free deposit
rate subtracted from the fund and the factors) and restructuring/reset
NAV jumps (>|25%|/day) are clipped — without those two corrections a
fund that merely earns the ~48% deposit rate, or has a one-day NAV
reset, reads as large spurious alpha.

**Classification.**

| Bucket | Rule |
|---|---|
| Closet index | R² ≥ 0.85 **and** 0.85 ≤ β_BIST ≤ 1.15 |
| True active | R² < 0.60 |
| Moderately active | everything else |

## Results

| Bucket | Funds | avg β_BIST | avg R² | avg α (annual) |
|---|---|---|---|---|
| Closet index | **52** | 0.93 | 0.94 | **−0.24** |
| Moderately active | 79 | 0.64 | 0.77 | −0.11 |
| True active | 105 | 0.49 | 0.21 | −0.39 |

The closet-index bucket self-validates: it contains the actual BIST30
index funds — which, correctly, now show alpha ≈ 0 (Garanti BIST30
+0.06, İş BIST30 +0.09, Ak BIST30 −0.06) — and alongside them major
bank-owned funds marketed as active, several at **R² > 0.95**: index
exposure at active fees.

Every bucket's average alpha is **≤ 0**. Two things drive that: (i) over
this high-rate sample the deposit rate outran BIST100, so equity
exposure was a poor excess-over-cash bet regardless of manager; and
(ii) the earlier version of this note reported a +1.49 "true active"
alpha that was an artefact of un-clipped NAV resets — the correction
removes it. **Read the alpha magnitudes as noisy** (annualized from
short-horizon intercepts in a single regime); the robust, citable
signal is the classification: ~1 in 5 large "active" equity funds runs
at index-like R² and β with **no positive alpha**.

## Why it matters

For an investor, "am I paying active fees for passive exposure?" is
directly answerable from public data. Once expense ratios are added,
the natural extension is an *active value* metric (`alpha − fees`)
identifying funds that systematically destroy value — the most
commercially relevant output this platform can produce.

## Limitations

R² thresholds are conventions, not laws; a factor model with BIST100
only (no size/style factors) can overstate "activeness" for small-cap
tilted funds. Alpha is gross of fees (no fee data yet) and regime-bound
(2.5-year, high-rate sample). The counts drift as the universe and data
grow — treat them as point-in-time, and see the [rigor
gate](../../tefaslab/rigor.py) (`research gate`) for the
multiple-testing view of which alphas survive at all.

*Reproduce:* `python -m tefaslab research closet --min-aum 500`
