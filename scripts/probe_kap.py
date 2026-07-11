"""Probe KAP endpoints: company list and disclosure query API."""
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
     "Accept": "application/json"}

candidates = [
    ("GET", "https://www.kap.org.tr/tr/api/kapmembers?type=IGS", None),
    ("GET", "https://www.kap.org.tr/tr/api/company/generic", None),
    ("GET", "https://www.kap.org.tr/tr/bist-sirketler", None),
    ("POST", "https://www.kap.org.tr/tr/api/memberDisclosureQuery",
     {"fromDate": "2026-07-01", "toDate": "2026-07-10",
      "disclosureClass": "FR", "market": "IGS"}),
]

for method, url, payload in candidates:
    try:
        if method == "GET":
            r = requests.get(url, headers=H, timeout=20)
        else:
            r = requests.post(url, json=payload,
                              headers={**H, "Content-Type": "application/json"},
                              timeout=20)
        ct = r.headers.get("Content-Type", "")
        print(f"{r.status_code} {method} {url[:70]} [{ct[:40]}] "
              f"{r.text[:150]!r}")
    except Exception as e:
        print(f"ERR {method} {url[:70]}: {e}")
