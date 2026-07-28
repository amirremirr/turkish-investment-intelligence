# Data Corrections, Privacy & Public-Research Policy

## Scope and limitations

This product uses public market data from TEFAS, KAP, TCMB EVDS, and Yahoo.
It provides research and education only, not investment advice, execution, or
personalized recommendations. Source freshness, coverage, calculation limits,
and methodology are displayed or documented with each relevant product area.

## Source use, availability and legal posture

The service uses each source only for public-market research and education:

| Source | Data used | Operational limit |
|---|---|---|
| TEFAS | Fund NAV, AUM, investor and allocation data | Unofficial JSON endpoints may throttle or change shape. |
| KAP | Public fund portfolio disclosures and attachments | Export and document endpoints can be flaky; holdings coverage is forward-built and template-dependent. |
| Yahoo Finance | Benchmark, stock-price and delayed quote data | Free endpoints can rate-limit or have ticker/split gaps. |
| TCMB EVDS | Macro series | Requires an API key and individual series can be rebased or retired. |

These sources have no service-level agreement with this project. They are not
treated as a license to redistribute source material or as an endorsement by a
source. Before a commercial launch, the service owner must review each current
source's terms, attribution requirements, rate limits, and permitted-use terms
with qualified counsel where appropriate. If a source disallows the intended
use, its dependent feature must be disabled or moved to a licensed feed.

Raw source payloads are retained only where needed for reproducibility and
correction investigation, are excluded from version control, and are not
published as a substitute for the original source. The product publishes
derived research metrics and links users to the source limitations instead of
claiming source ownership.

## Coverage and metric limits

- Fund coverage is not a complete history of every Turkish vehicle: closed
  funds from before the retained period are absent, and product-type coverage
  must be read from the data-status page before making universe-wide claims.
- KAP holdings are forward-built, report-dependent, and may lack usable
  weights; no absent holding should be interpreted as a confirmed zero.
- Alpha, closet-index and active-value research is **gross of fees** until a
  dated fee source is added. It measures exposure and gross outcomes, not an
  investor's net return.

## Corrections

If a published figure is materially wrong, stale beyond its stated freshness,
or based on a source defect:

1. stop or qualify the affected claim;
2. preserve the relevant snapshot, run log, source payload where permitted,
   and code revision;
3. repair and rerun the pipeline from reproducible inputs;
4. record the correction in the relevant report or release note, including the
   affected period and the nature of the change; and
5. retain the prior snapshot for auditability.

Do not silently rewrite a material published research conclusion.

## Privacy and security

The application does not collect user accounts, investment positions, or other
personal financial data. Operational access is limited to repository secrets
and the server-side serving database credential. Credentials must never be
committed, included in reports, or sent to client-side code. A suspected secret
exposure requires immediate credential rotation and a repository-history review.

## Requests and contact

Report data concerns, correction requests, or security issues through the
repository issue tracker. Do not post credentials or personal information in a
public issue.
