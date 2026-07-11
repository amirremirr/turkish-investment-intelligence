"""Try EVDS URL/auth variants to find the working combination."""
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
KEY = os.environ["EVDS_API_KEY"]

variants = [
    ("path-style + header key",
     "https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0"
     "&startDate=01-01-2026&endDate=11-07-2026&type=json", True, {}),
    ("query-style + header key",
     "https://evds2.tcmb.gov.tr/service/evds/?series=TP.FG.J0"
     "&startDate=01-01-2026&endDate=11-07-2026&type=json", True, {}),
    ("path-style + key param",
     "https://evds2.tcmb.gov.tr/service/evds/series=TP.FG.J0"
     "&startDate=01-01-2026&endDate=11-07-2026&type=json&key=" + KEY,
     False, {}),
    ("serieList endpoint + header",
     "https://evds2.tcmb.gov.tr/service/evds/serieList/type=json"
     "&code=TP.FG.J0", True, {}),
]

for label, url, use_header, extra in variants:
    headers = {"key": KEY} if use_header else {}
    headers["User-Agent"] = "Mozilla/5.0"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        ct = r.headers.get("Content-Type", "")
        ok = "json" in ct
        print(f"{r.status_code} {'JSON' if ok else ct[:25]:<25} {label}")
        if ok:
            print("   ", r.text[:200])
    except Exception as e:
        print(f"ERR  {label}: {e}")
