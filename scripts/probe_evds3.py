"""Probe the evds3 igmevdsms-dis service path variants."""
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
KEY = os.environ["EVDS_API_KEY"]

qs = "series=TP.FG.J0&startDate=01-01-2026&endDate=11-07-2026&type=json"
paths = [
    f"https://evds3.tcmb.gov.tr/igmevdsms-dis/{qs}",
    f"https://evds3.tcmb.gov.tr/igmevdsms-dis/evds/{qs}",
    f"https://evds3.tcmb.gov.tr/igmevdsms-dis/service/evds/{qs}",
    f"https://evds3.tcmb.gov.tr/igmevdsms-dis/?{qs}",
]
for url in paths:
    try:
        r = requests.get(url, headers={"key": KEY,
                                       "User-Agent": "Mozilla/5.0"},
                         timeout=30)
        ct = r.headers.get("Content-Type", "")
        print(f"{r.status_code} {ct[:28]:<28} {url[:80]}")
        if "json" in ct:
            print("   ", r.text[:250])
    except Exception as e:
        print(f"ERR {url[:70]}: {e}")
