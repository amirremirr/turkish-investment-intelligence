"""Download the IUF monthly portfolio PDF, strip the Java-serialization
wrapper, and check its granularity (asset-class vs stock-level)."""
import io
import re

import requests
from pypdf import PdfReader

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

# attachment objId from the 1604200 disclosure page
page = requests.get("https://www.kap.org.tr/tr/Bildirim/1604200",
                    headers=H, timeout=60).text
obj_ids = re.findall(r'objId\\":\\"([0-9a-f]{32})', page)
print("objIds:", obj_ids)

raw = requests.get("https://www.kap.org.tr/tr/api/file/download/"
                   + obj_ids[0], headers=H, timeout=120).content
print("raw bytes:", len(raw), "head:", raw[:8])

start = raw.find(b"%PDF")
print("pdf starts at offset:", start)
pdf = raw[start:]
open("data/kap_scan/IUF_2026_04.pdf", "wb").write(pdf)

reader = PdfReader(io.BytesIO(pdf))
print("pages:", len(reader.pages))
text = "\n".join((p.extract_text() or "") for p in reader.pages[:4])
print("\n---- first 2500 chars ----")
print(text[:2500])
