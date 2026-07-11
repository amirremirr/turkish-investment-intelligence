"""KAP scoping, round 3 — the decisive tests.

1. Are the per-disclosure APIs (excel export, file download) usable
   with plain requests, or bot-blocked like the query APIs?
2. Where does the fon-bildirimleri page fetch its disclosure list?
3. Does the disclosure-search page render results server-side when
   query params are passed in the URL?
"""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
     "Referer": "https://www.kap.org.tr/tr/Bildirim/1560337"}
S = requests.Session()
# warm cookies from an SSR page first
S.get("https://www.kap.org.tr/tr/Bildirim/1560337", headers=H, timeout=60)

print("== 1. per-disclosure APIs ==")
for label, url in [
    ("excel export", "https://www.kap.org.tr/tr/api/notification/export/"
                     "excel/1560337"),
    ("file download", "https://www.kap.org.tr/tr/api/file/download/"
                      "4028328d9c81f588019c89b088cb14c7"),
]:
    try:
        r = S.get(url, headers=H, timeout=60)
        ct = r.headers.get("Content-Type", "")
        head = r.content[:60]
        print(f"  {label}: {r.status_code} {ct[:45]} "
              f"bytes={len(r.content)} head={head[:24]!r}")
    except Exception as e:
        print(f"  {label}: ERR {e}")

print("\n== 2. fon-bildirimleri fetch target (JS hunt) ==")
url = ("https://www.kap.org.tr/tr/fon-bildirimleri/"
       "aft-ak-portfoy-yeni-teknolojiler-yabanci-hisse-senedi-fonu")
r = S.get(url, headers=H, timeout=60)
text = r.text
ids = set(re.findall(r"\b1[0-9]{6}\b", text))
print(f"  page {r.status_code} {len(text)}B; embedded id-like numbers: "
      f"{sorted(ids)[:8]}")
chunks = sorted(set(re.findall(r'src="(/_next/static/[^"]+\.js)"', text)))
hits = {}
for c in chunks[:25]:
    try:
        js = S.get("https://www.kap.org.tr" + c, headers=H, timeout=60).text
    except Exception:
        continue
    for m in re.findall(
            r'["\'`]((?:https://[a-z0-9.]*kap\.org\.tr)?/[a-zA-Z0-9_\-/]'
            r'{2,50}(?:bildirim|Bildirim|disclosure|Disclosure|'
            r'notification|query|sorgu)[a-zA-Z0-9_\-/]{0,50})["\'`]', js):
        hits[m] = hits.get(m, 0) + 1
print(f"  scanned {min(len(chunks), 25)}/{len(chunks)} chunks")
for path, n in sorted(hits.items()):
    print(f"   {n}x {path}")

print("\n== 3. SSR disclosure search with URL params ==")
for u in [
    "https://www.kap.org.tr/tr/bildirim-sorgulari?fundOid="
    "33E5FED7E77300EAE0530A4A622B2AEA",
    "https://www.kap.org.tr/tr/bildirim-sorgu?mkkMemberOid="
    "4028e4a240e8d16e0140e8f3623d0043",
]:
    try:
        r = S.get(u, headers=H, timeout=60)
        n_ids = len(set(re.findall(r"/tr/Bildirim/(\d+)", r.text)))
        print(f"  {r.status_code} ids={n_ids} {u[:75]}")
    except Exception as e:
        print(f"  ERR {u[:60]}: {e}")
