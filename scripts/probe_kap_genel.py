"""Probe the fund 'genel' page and one disclosure page."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

for url in [
    "https://www.kap.org.tr/tr/fon-bilgileri/genel/"
    "aft-ak-portfoy-yeni-teknolojiler-yabanci-hisse-senedi-fonu",
    "https://www.kap.org.tr/tr/Bildirim/1560337",
]:
    r = requests.get(url, headers=H, timeout=30)
    text = r.text
    print(f"\n=== {r.status_code} {url[:80]} ({len(text)} bytes)")
    i = text.find("portfoy_dagilim")
    if i == -1:
        i = text.find("Portföy Dağılım")
    if i > 0:
        chunk = text[i:i + 1200].replace("\\", "")
        print("portfolio section:", chunk[:1000])
    att = sorted(set(re.findall(r'"(/[^"]*(?:ek|Ek|attachment|download)[^"]*)"',
                                text)))
    print("attachment-ish links:", att[:8])
    pct = re.findall(r'([A-ZÇĞİÖŞÜ ]{4,40})\s*[:%]?\s*%\s*([\d.,]+)', text)
    print("percent patterns:", pct[:8])
