"""Scan a range of disclosure ids via the (open) excel-export endpoint
and classify what lives there — specifically hunting fund portfolio /
financial reports with stock-level tables."""
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

START = int(sys.argv[1]) if len(sys.argv) > 1 else 1604200
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 120

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
S = requests.Session()
OUT = Path("data/kap_scan")
OUT.mkdir(parents=True, exist_ok=True)

types = Counter()
fund_hits = []
for did in range(START, START + COUNT):
    url = f"https://www.kap.org.tr/tr/api/notification/export/excel/{did}"
    try:
        r = S.get(url, headers=H, timeout=30)
    except Exception:
        time.sleep(2)
        continue
    if r.status_code != 200 or len(r.content) < 500:
        types["<empty/err>"] += 1
        time.sleep(0.7)
        continue
    text = r.content.decode("utf-8", errors="ignore")
    # crude title/type extraction from the export html
    title = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
    title = (title.group(1).strip()[:70] if title else "?")
    is_fund = ("FONU" in text.upper()[:4000]
               or "PORTFÖY" in text.upper()[:4000])
    kind = "?"
    for kw in ("Portföy Dağılım", "Fon Sürekli Bilgilendirme",
               "Finansal Rapor", "Performans Sunum", "Yatırımcı Bilgi",
               "İzahname", "Fon Portföy Değer", "Pay Alım Satım",
               "Özel Durum", "Değerleme Raporu"):
        if kw.lower() in text.lower():
            kind = kw
            break
    types[kind] += 1
    if is_fund and kind in ("Portföy Dağılım", "Finansal Rapor",
                            "Fon Portföy Değer", "Fon Sürekli Bilgilendirme"):
        fund_hits.append((did, kind, title))
        (OUT / f"{did}_{kind.replace(' ', '_')}.html").write_bytes(r.content)
    time.sleep(0.7)

print(f"scanned {COUNT} ids from {START}")
print("\ntype tally:")
for k, n in types.most_common():
    print(f"  {n:>4} {k}")
print(f"\nfund report hits ({len(fund_hits)}):")
for did, kind, title in fund_hits[:20]:
    print(f"  {did} [{kind}] {title}")
