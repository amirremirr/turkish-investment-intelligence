"""Probe KAP fund list page and a fund detail page."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

s = requests.Session()
r = s.get("https://www.kap.org.tr/tr/YatirimFonlari/YF", headers=H,
          timeout=30)
print(f"fund list YF: {r.status_code} ({len(r.text)} bytes)")

# find fund codes / detail links
for pat in (r'"fundCode\\?":\\?"([A-Z0-9]+)\\?"',
            r'href="(/tr/fon[^"]{5,80})"',
            r'href="(/tr/[^"]*[Ff]on[^"]{5,80})"'):
    hits = sorted(set(re.findall(pat, r.text)))
    print(pat[:40], "->", len(hits), hits[:8])

# dump a chunk around a known fund code if present
for code in ("AFT", "MAC", "TI2"):
    i = r.text.find(f'"{code}"')
    if i == -1:
        i = r.text.find(code)
    if i > 0:
        print(f"\ncontext around {code}:")
        print(r.text[i - 300:i + 300].replace("\\", "")[:600])
        break
