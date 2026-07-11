"""List disclosure types on a fund's fon-bildirimleri page."""
import re
from collections import Counter

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

url = ("https://www.kap.org.tr/tr/fon-bildirimleri/"
       "aft-ak-portfoy-yeni-teknolojiler-yabanci-hisse-senedi-fonu")
r = requests.get(url, headers=H, timeout=30)
text = r.text
print(f"{r.status_code} ({len(text)} bytes)")

ids = sorted(set(re.findall(r'/tr/Bildirim/(\d+)', text)))
print(f"disclosure links: {len(ids)}, e.g. {ids[:5]}")

# disclosure titles usually appear as JSON fields
for key in ("title", "konu", "subject", "disclosureType", "baslik"):
    hits = re.findall(rf'\\"{key}\\":\\"(.*?)\\"', text)
    if hits:
        c = Counter(hits)
        print(f"\n{key}: {len(hits)} values, top:")
        for v, n in c.most_common(8):
            print(f"   {n}x {v[:70]}")
