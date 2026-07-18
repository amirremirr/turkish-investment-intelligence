"""Operational source-contract canary.

The unit tests (ci.yml) run offline; the health monitor (monitor.yml)
inspects the *serving DB* after the fact. Neither notices when an
UPSTREAM source changes shape or goes away — that only surfaces when the
nightly pipeline trips over it (or, worse, silently ingests garbage).

This makes one minimal real request to each source and drives the SAME
fetch path — and the same contract assertions — the pipeline uses, so a
silent TEFAS / KAP / Yahoo / EVDS schema change is caught here, by CI on
a schedule, instead of by a user staring at stale numbers. Reusing the
real clients keeps the contract defined in exactly one place
(tefaslab/*), so this canary can never drift out of sync with what the
pipeline actually depends on.

Per source:
  OK       valid response, shaped as expected
  CHANGED  a contract assertion fired — schema/template moved, needs eyes
  DOWN     unreachable after the client's own retries + one outer retry
  SKIP     precondition missing (e.g. no EVDS key in this environment)

Exits non-zero if any source is CHANGED or DOWN, which makes the
workflow open/refresh a GitHub issue. DOWN can occasionally be a
transient blip; sustained outages are also caught downstream by the
daily freshness monitor, so this errs toward surfacing early.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

# Run as a script -> scripts/ is on sys.path, not the repo root; put the
# repo root first so `import tefaslab` works from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK, CHANGED, DOWN, SKIP = "OK", "CHANGED", "DOWN", "SKIP"
ICON = {OK: "[ OK ]", CHANGED: "[CHG!]", DOWN: "[DOWN]", SKIP: "[skip]"}

# Recent window wide enough to span a weekend / short holiday so an
# empty result means "source problem", not "no trading that day".
_WINDOW_DAYS = 8
# Substrings the TEFAS client uses only in *contract* failures — lets us
# label a shape change vs a plain outage. Cosmetic: both still alert.
_TEFAS_CONTRACT = ("schema likely changed", "no 'resultList'",
                   "may have been dropped", "missing expected fields")
# A permanent SPK portfolio-report disclosure (regulatory filings are
# not deleted) — the marker the KAP scanner keys on must stay present.
_KAP_CANARY_ID = 1604105


def _window() -> tuple[date, date]:
    end = date.today()
    return end - timedelta(days=_WINDOW_DAYS), end


def _classify_tefas(err: Exception) -> tuple[str, str]:
    msg = str(err)
    return (CHANGED if any(m in msg for m in _TEFAS_CONTRACT) else DOWN), msg


def check_tefas_history() -> tuple[str, str]:
    from tefaslab import client
    start, end = _window()
    try:
        rows = client.fetch_history(client.make_session(), start, end,
                                    fund_type="YAT")
    except client.TefasError as e:
        return _classify_tefas(e)
    if not rows:
        return DOWN, f"no YAT NAV rows in the last {_WINDOW_DAYS} days"
    r = rows[0]
    try:  # the contract check guards keys; also assert price is numeric
        float(r["fiyat"])
    except (TypeError, ValueError, KeyError):
        return CHANGED, f"'fiyat' not numeric: {r.get('fiyat')!r}"
    return OK, f"{len(rows)} rows, latest {r.get('tarih')}"


def check_tefas_alloc() -> tuple[str, str]:
    from tefaslab import client
    start, end = _window()
    try:
        rows = client.fetch_allocation(client.make_session(), start, end,
                                       fund_type="YAT")
    except client.TefasError as e:
        return _classify_tefas(e)
    if not rows:
        return DOWN, f"no YAT allocation rows in the last {_WINDOW_DAYS} days"
    return OK, f"{len(rows)} rows, {len(rows[0])} columns"


def check_yahoo() -> tuple[str, str]:
    from tefaslab import benchmarks
    start = (date.today() - timedelta(days=_WINDOW_DAYS)).isoformat()
    s = benchmarks._closes("XU100.IS", start)
    if s is None or len(s) == 0:
        return DOWN, "XU100.IS returned no closes (Yahoo down or ticker gone)"
    last = float(s.iloc[-1])
    if not last > 0:
        return CHANGED, f"XU100.IS last close not positive: {last}"
    return OK, f"XU100.IS {len(s)} closes, last {last:,.0f}"


def check_kap() -> tuple[str, str]:
    import requests
    from tefaslab import kap
    r = requests.get(kap.EXPORT.format(_KAP_CANARY_ID), headers=kap.H,
                     timeout=30)
    if r.status_code != 200 or len(r.content) < 500:
        return DOWN, (f"export HTTP {r.status_code}, {len(r.content)}B "
                      "(KAP export endpoint down/empty)")
    text = r.content.decode("utf-8", errors="ignore")
    if "Portföy Dağılım Raporu" not in text:
        return CHANGED, ("export no longer contains the 'Portföy Dağılım "
                         "Raporu' marker — KAP disclosure template changed")
    return OK, f"canary #{_KAP_CANARY_ID} export OK ({len(r.content)}B)"


def check_evds() -> tuple[str, str]:
    from tefaslab import evds
    key = evds.api_key()
    if not key:
        return SKIP, "EVDS_API_KEY not set in this environment"
    code = evds.SERIES["cpi_index"]
    try:
        rows = evds.fetch_series(key, code, start="01-01-2026")
    except evds.EvdsError as e:
        return CHANGED, str(e)  # non-JSON => endpoint moved or key rejected
    if not rows:
        return CHANGED, (f"{code}: JSON parsed but no points — series or "
                         "column name changed")
    d, v = rows[-1]
    return OK, f"{code} {len(rows)} points, last {d}={v}"


CHECKS = [
    ("TEFAS - NAV history", check_tefas_history),
    ("TEFAS - allocations", check_tefas_alloc),
    ("Yahoo - benchmarks", check_yahoo),
    ("KAP - disclosures", check_kap),
    ("EVDS - macro", check_evds),
]


def _run(fn) -> tuple[str, str]:
    try:
        return fn()
    except Exception as e:  # any unexpected failure = treat as reachable-but
        return DOWN, f"unexpected {type(e).__name__}: {e}"


def main() -> int:
    now = datetime.now(timezone.utc)
    print(f"Source contract check - {now:%Y-%m-%d %H:%M} UTC\n")
    results = []
    for label, fn in CHECKS:
        status, detail = _run(fn)
        if status == DOWN:  # one outer retry to absorb a transient blip
            time.sleep(15)
            status, detail = _run(fn)
        results.append((label, status, detail))
        print(f"{ICON[status]} {label:<22} {detail}")

    changed = [r for r in results if r[1] == CHANGED]
    down = [r for r in results if r[1] == DOWN]
    print()
    if changed or down:
        parts = []
        if changed:
            parts.append(f"{len(changed)} CHANGED (schema/contract)")
        if down:
            parts.append(f"{len(down)} DOWN (unreachable)")
        print("FAIL: " + ", ".join(parts) + " - see lines marked above.")
        return 1
    print("All sources reachable and shaped as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
