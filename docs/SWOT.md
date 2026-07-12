# SWOT — honest self-assessment

*Last reviewed 2026-07-12. Weaknesses and threats are tracked here on
purpose: a platform that hides its limits can't be trusted on its
strengths.*

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
   see [SUPABASE.md](SUPABASE.md)). ~~Windows-centric ops~~ — pipeline
   runs on GitHub Actions. ~~No multi-user serving path~~ — a curated
   serving copy publishes to Supabase Postgres after each pipeline run
   (REST/auth-ready); the Next.js frontend remains future work.
2. **Testing depth**: unit tests now cover the critical logic (lag
   convention, flow guard, classifier, OLS, KAP parser), but coverage
   is thin elsewhere; no integration tests against live APIs.
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
