"""TCMB EVDS macro data (CPI, policy rate, deposit rates).

Endpoint (verified 2026-07-11): the EVDS service migrated from
evds2.tcmb.gov.tr/service/evds/ to evds3.tcmb.gov.tr/igmevdsms-dis/
(same param style, API key in the `key` header). The key lives in the
EVDS_API_KEY env var or a gitignored .env file — never in code.

Series are stored in the shared `benchmarks` table:
    cpi_index    monthly CPI level (TP.FG.J0, 2003=100; ~1 month lag)
    policy_rate  CBRT average funding cost, % (TP.APIFON4, daily)
    deposit_3m   3-month TL deposit rate, % (TP.TRY.MT02, weekly)
    deposit_1y   1-year TL deposit rate, % (TP.TRY.MT04, weekly)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import requests

from . import db

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

SERIES = {
    "cpi_index": "TP.FG.J0",
    "policy_rate": "TP.APIFON4",
    "deposit_3m": "TP.TRY.MT02",
    "deposit_1y": "TP.TRY.MT04",
}


class EvdsError(RuntimeError):
    pass


def api_key() -> str | None:
    if os.environ.get("EVDS_API_KEY"):
        return os.environ["EVDS_API_KEY"]
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("EVDS_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def _parse_date(raw: str) -> str:
    """EVDS dates: '02-01-2024' (daily/weekly) or '2026-1' (monthly)."""
    if "-" in raw and len(raw.split("-")[0]) == 4:      # 2026-1
        y, m = raw.split("-")
        return f"{int(y):04d}-{int(m):02d}-01"
    d, m, y = raw.split("-")                            # dd-mm-yyyy
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def fetch_series(key: str, code: str, start: str = "01-01-2024",
                 end: str | None = None) -> list[tuple[str, float]]:
    end = end or date.today().strftime("%d-%m-%Y")
    url = (f"{BASE}/series={code}&startDate={start}&endDate={end}"
           "&type=json")
    r = requests.get(url, headers={"key": key, "User-Agent": "Mozilla/5.0"},
                     timeout=60)
    if "json" not in r.headers.get("Content-Type", ""):
        raise EvdsError(f"{code}: non-JSON response ({r.status_code}) — "
                        "endpoint or key problem")
    col = code.replace(".", "_")
    out = []
    for item in r.json().get("items") or []:
        val = item.get(col)
        if val in (None, ""):
            continue
        out.append((_parse_date(item["Tarih"]), float(val)))
    return out


def fetch_macro(db_path=db.DB_PATH) -> dict:
    """Fetch all EVDS series into the benchmarks table."""
    key = api_key()
    if not key:
        print("  EVDS_API_KEY not set — skipping macro fetch")
        return {}
    conn = db.connect(db_path)
    counts = {}
    for name, code in SERIES.items():
        rows = [(name, d, v) for d, v in fetch_series(key, code)]
        db.upsert_benchmarks(conn, rows)
        counts[name] = len(rows)
        print(f"  {name:<12} {code:<14} {len(rows)} rows")
    conn.commit()
    conn.close()
    return counts
