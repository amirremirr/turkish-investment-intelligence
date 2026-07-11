"""Pull the Siber Güvenlik fund's portfolio PDF and verify stock rows."""
import io
import re
from collections import Counter

import requests
from pypdf import PdfReader

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

page = requests.get("https://www.kap.org.tr/tr/Bildirim/1604196",
                    headers=H, timeout=60).text
objs = re.findall(r'objId\\":\\"([0-9a-f]{32})', page)
print("objIds:", objs)
raw = requests.get("https://www.kap.org.tr/tr/api/file/download/" + objs[0],
                   headers=H, timeout=120).content
pdf = raw[raw.find(b"%PDF"):]
open("data/kap_scan/IJZ_portfolio.pdf", "wb").write(pdf)
reader = PdfReader(io.BytesIO(pdf))
full = "\n".join((p.extract_text() or "") for p in reader.pages)
print("pages:", len(reader.pages), "chars:", len(full))

isins = re.findall(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", full)
by_country = Counter(i[:2] for i in set(isins))
print("unique ISINs:", len(set(isins)), "by country:", dict(by_country))

i = full.find("HİSSE SENETLERİ")
if i == -1:
    i = full.find("PORTFÖY DEĞERİ TABLOSU")
print("---- equity table region ----")
print(full[i:i + 1200])
