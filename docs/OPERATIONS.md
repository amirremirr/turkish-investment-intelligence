# Operations, Releases & Incident Response

## Service ownership and objectives

The repository owner is the service owner until a named successor is recorded
here. The owner reviews failed GitHub Actions runs and open monitoring issues
on business days.

| Severity | Example | Target acknowledgement | Target restoration |
|---|---|---:|---:|
| P1 | Public site is serving stale or materially wrong data | 4 business hours | 1 business day |
| P2 | A non-critical dataset or research page is unavailable | 1 business day | 3 business days |
| P3 | Cosmetic defect, enhancement, or documentation issue | 3 business days | Planned backlog |

These are operating targets, not guarantees. The platform is research and
education software, not an execution, custody, or advisory service.

## Release controls

1. Every change lands through a pull request when practical.
2. Required checks are Python tests/import smoke, web lint/typecheck, security
   scans, and the production web build on `main`.
3. A production change must not be announced until the post-pipeline serving
   health check is green.
4. Dependency upgrades are reviewed through Dependabot pull requests; do not
   manually loosen `requirements.lock` ranges.
5. Roll back code by reverting the change. Restore data only from an integrity
   checked GitHub Release snapshot, then republish it deliberately.

## Incident playbook

1. Open the failed Action or health-monitor issue and identify whether the
   failure is ingestion, analytics, publishing, serving DB, or web rendering.
2. Freeze any public claim affected by suspected bad data; add a status note if
   figures could mislead users.
3. Preserve the run logs and snapshot tag. Do not overwrite the database until
   the failure mode is understood.
4. Fix or revert, run the relevant workflow manually, then confirm both the
   pipeline and serving-health jobs are green.
5. For a material correction, follow `DATA_POLICY.md`, close the incident with
   root cause and prevention, and link the corrective commit.

## Routine checks

- Daily: review failed Actions and any open system-health/source-contract issue.
- Weekly: verify the newest DB snapshot Release and dependency-update queue.
- Monthly: review coverage, source limitations, SLO misses, and open P2/P3s.
