# Data Corrections, Privacy & Public-Research Policy

## Scope and limitations

This product uses public market data from TEFAS, KAP, TCMB EVDS, and Yahoo.
It provides research and education only, not investment advice, execution, or
personalized recommendations. Source freshness, coverage, calculation limits,
and methodology are displayed or documented with each relevant product area.

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
