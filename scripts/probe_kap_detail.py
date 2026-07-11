"""Probe one KAP fund detail page for disclosures/portfolio reports."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

url = ("https://www.kap.org.tr/tr/fon-bilgileri/ozet/"
       "aft-ak-portfoy-yeni-teknolojiler-yabanci-hisse-senedi-fonu")
r = requests.get(url, headers=H, timeout=30)
print(f"{r.status_code} ({len(r.text)} bytes)")

text = r.text
# look for disclosure ids, attachment links, portfolio keywords
for pat, label in [
        (r'href="(/tr/Bildirim/[^"]+)"', "disclosure links"),
        (r'href="([^"]*ek-indir[^"]*)"', "attachment downloads"),
        (r'"disclosureIndex\\?":\\?"?(\d+)', "disclosure ids"),
        (r'[Pp]ortföy [Dd]ağılım', "portfolio keyword"),
        (r'href="(/tr/fon-bilgileri/[^"]+)"', "fund sub-pages")]:
    hits = re.findall(pat, text)
    uniq = sorted(set(hits))
    print(f"{label}: {len(uniq)}", uniq[:6])

# check for embedded JSON keys that look like holdings/allocation
for kw in ("stockCode", "hisseKodu", "portfoy", "allocation", "varlik"):
    n = text.count(kw)
    if n:
        i = text.find(kw)
        print(f"\nkeyword {kw} x{n}: ...{text[max(0,i-120):i+200]!r}")
