# SWOT — honest self-assessment

*Last reviewed 2026-07-17 (incl. an external critical review).
Weaknesses and threats are tracked here on purpose: a platform that
hides its limits can't be trusted on its strengths.*

## External review, 2026-07-17 — accepted findings

A detailed external critique was accepted essentially in full. Its
sharpest point: *the gap is not awareness — several UI surfaces still
behaved as if the documented limitations were solved.* Actions taken
same day:

- **Memo/scoring inconsistency fixed** — memos flagged raw
  `alpha > 10%` as a strength while the skill score ranks the
  t-statistic; memos now require `|t| > 2` and explicitly flag
  non-significant alpha as a *risk*.
- **Inference unified** — the single-fund factor model now computes the
  same overlap-corrected alpha t-stat as the batch path.
- **Limitations surfaced in the product, not only in docs** — the web
  homepage and research page now state the single-regime sample, the
  <1% R² of flow effects, non-tradability, and the fee-blindness of
  the closet-index study, directly next to the findings.
- **Single scheduler** — the local Windows daily task was deleted;
  GitHub Actions is the sole pipeline owner (divergent-DB risk closed).

Accepted but structural (tracked below / roadmap): four-factor model
simplicity, multiple-testing corrections, fund-level panel designs,
fee data, heuristic score weights, regime-table power. (Review
priority #1 — the cache-backed authoritative DB — is now durably
backed by weekly hash-frozen snapshot releases, see Weakness 1;
priority #2 — thin operational CI — is addressed by the twice-daily
source-contract canary, see Weakness 2.) Position statement: this
is a **personal research workstation with transparent methods** — not
institution-grade intelligence, and it should not be marketed as such.

## Strengths

- End-to-end automated pipeline (TEFAS + KAP + EVDS + Yahoo → SQLite →
  precomputed terminal) with health checks and status monitoring
- Methodological rigor: NAV-lag correction, Newey–West errors,
  out-of-sample validation, restructuring-guarded flows, alpha
  t-statistics, sensitivity-tested scores — all documented
- **Stock-level fund holdings** from public KAP disclosures (monthly,
  ISIN-by-ISIN) — data most retail tools don't have
- Reproducible research with published methodology and audit
- Unit-tested core logic + CI (added 2026-07-12)

## Weaknesses (open, prioritized)

1. **Infrastructure**: SQLite single-writer for compute (by design —
   see [SUPABASE.md](SUPABASE.md)); the Next.js web app is live on the
   Supabase serving copy. The compute-DB seam is now *durably backed*:
   a weekly job (`.github/workflows/snapshot.yml` → `scripts/snapshot.py`)
   `VACUUM INTO`s a clean copy, integrity-checks and floor-guards it,
   and uploads it plus a manifest to a **GitHub Release** — the manifest
   freezes a **data+code hash** (`db_sha256` + `git_sha`) so any cited
   finding is reproducible from the matching snapshot tag. The Actions
   cache stops being the only home for the irreplaceable forward-only
   KAP history. *Residual risk*: recovery point is up to one week; the
   snapshot restores from the same cache, so it can't recover from a
   silent mid-week corruption that also poisons the cache (mitigated by
   the pre-upload integrity + row-count floors, not eliminated). Note
   the price of SQLite lock-in still compounds monthly — acceptable now,
   but it must stay a *priced* decision, not a forgotten one.
2. **Testing depth**: unit tests cover the critical logic (lag
   convention, flow guard, classifier, OLS, KAP parser, snapshot/publish
   guards, canary exit codes). A scheduled **source-contract canary**
   (`source_check.yml` → `scripts/source_check.py`, 2×/day) now drives
   the real TEFAS/KAP/Yahoo/EVDS fetch paths and pages on a schema change
   — the remaining gap is depth (no full end-to-end pipeline run in CI,
   no assertion on parsed *values*, only response shape).
3. **Sample**: Jan 2024 → present, almost entirely restrictive-rate
   months. Regime comparisons lack power until an easing cycle enters
   the sample.
4. **Data gaps**: no fee data (closet-index = exposure, not net-of-fee
   value); BYF/GYF/GSYF not backfilled; pre-2024 closures absent;
   Yahoo small-cap quality; no BIST holiday calendar.
5. **KAP holdings**: forward-only history; flaky export endpoint
   (retry/rescan cycles); brute-force ID scanning; template-dependent
   parser (breaks loudly, not silently).
6. **Statistics**: residual diagnostics not implemented; cash-carry
   alpha requires category context (documented).
7. **Product**: no auth/multi-tenancy/API; Streamlit UX ceiling.

## Opportunities

1. **Holdings unlock** (highest value): active share, crowding,
   holdings-based closet detection, true stock-selection attribution,
   stock↔fund explorer.
2. **Productization**: screener + alerts on presentation tables; API
   layer; research terminal for advisors/fintechs targeting Turkish
   retail.
3. **Data expansion**: BYF/GYF/GSYF universes; fee data → net-of-fee
   metrics; Postgres when multi-user.
4. **Research credibility**: publish notes externally; regime analysis
   matures as the sample spans an easing cycle; EM behavioral-finance
   collaboration potential.
5. **Modernization**: Docker + cloud cron; CI already runs tests on
   every push.
6. **Positioning**: Turkey's fund market is data-rich but analytically
   underserved — professional-grade questions are a real gap.

## Threats (with mitigations)

1. **Source fragility**: TEFAS/KAP/Yahoo can change or block at any
   time (no SLA). *Mitigation*: health checks + per-source freshness
   monitoring surface breakage immediately; parsers fail loudly.
2. **Misinterpretation**: institutional-looking outputs used without
   reading caveats (category context, sample length, cash carry).
   *Mitigation*: caveats embedded in outputs themselves (memo/report
   text), not only in docs; "not investment advice" throughout.
3. **Regime dependency**: signals calibrated in a 40%-inflation,
   restrictive environment may reverse in an easing cycle.
   *Mitigation*: regime engine labels the environment; findings are
   dated and sample-scoped.
4. **Competition**: commercial terminals or local fintech apps could
   ship similar analytics with better distribution. *Mitigation*: the
   moat is methodology + holdings depth, not UI.
5. **Bus factor**: solo-maintained, deep domain logic. *Mitigation*:
   documentation-first culture (methodology/audit/data dictionary),
   CI, loud failure modes.
