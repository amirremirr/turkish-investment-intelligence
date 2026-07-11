"""Verify all needed EVDS series on the working evds3 endpoint."""
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
KEY = os.environ["EVDS_API_KEY"]
BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

candidates = {
    "CPI index (TP.FG.J0)": "TP.FG.J0",
    "CBRT avg funding cost (TP.APIFON4)": "TP.APIFON4",
    "1w repo rate (TP.APIFON1)": "TP.APIFON1",
    "deposit 3m TL (TP.TRY.MT02)": "TP.TRY.MT02",
    "deposit 1y TL (TP.TRY.MT04)": "TP.TRY.MT04",
}

for label, code in candidates.items():
    url = (f"{BASE}/series={code}&startDate=01-01-2024&"
           f"endDate=11-07-2026&type=json")
    try:
        r = requests.get(url, headers={"key": KEY,
                                       "User-Agent": "Mozilla/5.0"},
                         timeout=30)
        if "json" not in r.headers.get("Content-Type", ""):
            print(f"---  {label}: non-JSON ({r.status_code})")
            continue
        body = r.json()
        items = body.get("items") or []
        first = next((i for i in items if any(
            v for k, v in i.items() if k.startswith("TP"))), {})
        last = next((i for i in reversed(items) if any(
            v for k, v in i.items() if k.startswith("TP"))), {})
        val = [v for k, v in last.items()
               if k.startswith("TP") and v][:1]
        print(f"OK   {label}: {len(items)} rows, "
              f"{first.get('Tarih')}..{last.get('Tarih')}, last={val}")
    except Exception as e:
        print(f"ERR  {label}: {e}")
