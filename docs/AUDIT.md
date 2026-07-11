# Institutional Readiness Audit

*Performed 2026-07-11 against the live database (1.06M fund-price rows,
Jan 2024 – Jul 2026). Reproduce with `python scripts/audit.py`. The
framing question: if this platform were handed to an investment
research team tomorrow, what would break, what would be questioned,
and what would prevent someone from trusting it?*

## Summary

| Dimension | Verdict |
|---|---|
| Data integrity | PASS with documented caveats |
| Flow methodology | **1 critical artifact found and fixed** |
| Factor model | PASS — no multicollinearity, betas stable, t-stats added |
| Score robustness | PASS — rankings insensitive to weight perturbation |
| Repo hygiene | PASS — no data/secrets tracked |
| Known gaps | pension funds absent; no fee data; single-regime sample |

---

## 1. Data layer

| Check | Result | Status |
|---|---|---|
| Negative NAVs | 0 rows | ✅ |
| Zero-AUM rows | 962 rows (0.09%) — reporting gaps in small funds; excluded from AUM-based metrics via null handling | ⚠ documented |
| Investor-count 10× daily jumps | 19 events across 17 funds — institutional block entries/exits or reporting corrections; not filtered, flagged for per-fund analysis | ⚠ documented |
| Duplicate (code, date) | impossible — primary key | ✅ |
| Dead funds retained | 25 funds with no price for 30+ days remain in the DB with full history | ✅ |
| Universe coverage | 1,306 funds (Jan 2024) → 2,033 (Jul 2026); the universe grows with the market rather than being fixed retroactively | ✅ |
| **Survivorship** | funds alive at any point since Jan 2024 are permanently retained; funds closed *before* 2024 are absent — rankings over the sample window are survivorship-clean, but "since inception" claims would not be | ⚠ documented |
| Fund types | **only YAT (mutual funds) ingested**; EMK/BYF/GYF/GSYF supported by the client but not yet backfilled | ❗ open gap |

## 2. Fund flows (Flow = ΔShares × NAV_t)

- **Price choice**: NAV at *t* (the day the share change is recorded).
  Using NAV_t makes the identity `flow ≡ ΔAUM − AUM·r` hold exactly.
- **Critical finding**: the single largest "flow" in the database was
  **PTE, 2025-05-12: −₺1.29 trillion coinciding with a +9,940% NAV
  move** — a unit restructuring, not investor money. This one row was
  large enough to distort market-level aggregates.
  **Fix applied**: flows are now excluded where |daily NAV return| >
  50% (`flows.MAX_NAV_MOVE`), and the guard is documented in
  METHODOLOGY §4.
- The remaining top flows (GAL, GJH: ₺70–95bn/day) are money-market
  funds with institutional cash sweeps — real flows, legitimately
  dominant, worth remembering when reading aggregate figures.
- AUM↑ while investors↓ occurs and is *not* treated as an error
  (large-holder concentration is a signal, not noise).

## 3. Factor model

**Factor correlations** (daily returns, full sample):

|  | bist100 | gold_try | usdtry | nasdaq_try |
|---|---|---|---|---|
| bist100 | 1.00 | 0.11 | −0.05 | 0.16 |
| gold_try | | 1.00 | 0.19 | 0.16 |
| usdtry | | | 1.00 | 0.18 |
| nasdaq_try | | | | 1.00 |

Max pairwise |r| = 0.19 → **no multicollinearity concern**. (The
worry that TRY-converted factors would embed USDTRY proved unfounded
at daily frequency, where local price moves dominate FX.)

**Beta stability** — YEF (BIST30 index fund) vs BIST100(+1 lag):
2024: 0.981 · 2025: 1.005 · 2026: 0.978. The lag-corrected model is
stable across years.

**Alpha significance** — raw alphas are no longer ranked. `dash_betas`
now carries an **alpha t-statistic** with a ~K-fold variance inflation
for the overlapping-return serial correlation (conservative,
Hansen–Hodrick-style). 631 of 2,003 funds (32%) show |t| > 2. The
Manager Skill score ranks the *t-statistic*, so a noisy 100% alpha on
three months of a tiny fund no longer outranks a precise 15% alpha.

**Residual diagnostics** (normality, heteroskedasticity) and full
Newey–West errors remain open items — noted in METHODOLOGY §8.

## 4. Score robustness (sensitivity analysis)

Skill-score weights perturbed ±5–10pp per component:

| Perturbation | Rank correlation | Top-20 overlap |
|---|---|---|
| 40/20/20/20 | 0.999 | 20/20 |
| 30/30/20/20 | 0.999 | 19/20 |
| 35/25/30/10 | 0.995 | 15/20 |

Rankings are **not fragile** — conclusions survive reasonable weight
changes. Cross-category comparability remains a caveat: scores are
percentile-based across the whole filtered universe; use `--category`
filters when comparing like with like.

## 5. Repo hygiene / security

- 56 tracked files; **no** `.db`, `.env`, `.log`, `data/` files tracked.
- No secret-like keywords in the codebase (no API keys exist yet; the
  EVDS key, when added, goes in an env var — never in code).

## 6. Open items

Resolved since the audit (same day):

1. ~~Ingest EMK pension funds~~ — backfilled 2024→present; nightly
   pipeline updates both YAT and EMK.
2. ~~Newey–West standard errors~~ — implemented (Bartlett kernel, lag =
   overlap); findings *strengthened*: contrarian flows NW t = −2.5,
   performance chasing NW t = 4.3.
3. ~~Out-of-sample split~~ — `research flows-oos`: 2026 holdout shows
   the same sign and magnitude (β −1.29 vs −1.09 trained).
4. ~~Category-normalized scoring~~ — `quality --within-category`; also
   added `research diagnostics` (per-category factor sanity: equity
   loads on BIST 0.65, gold funds on gold 0.93, money market on
   nothing). It exposed the **cash-carry caveat**: 100% of money-market
   funds show "significant alpha" that is deposit interest, not skill —
   documented in METHODOLOGY §7.

Still open (prioritized):

5. Fee data → net-of-fee closet-index "active value" metric.
6. BIST holiday calendar for stock-data gap detection.
7. Residual diagnostics (normality, heteroskedasticity) for the factor
   model.
