"""HTTP client for the TEFAS JSON API (the endpoints behind
tefas.gov.tr/tr/fon-verileri).

  POST /api/funds/fonGnlBlgSiraliGetir  -> daily NAV, shares, investors, AUM
  POST /api/funds/dagilimSiraliGetirT   -> daily portfolio asset-class weights

Both take a JSON payload with yyyymmdd dates and row-number pagination
(basSira/bitSira). The server rejects ranges longer than 1 month
("Tarih aralığı 1 ayı aşamaz"), so callers chunk by 28 days (ingest.py).
The HTML site sits behind an F5 anti-bot challenge but the API does not.
"""

from __future__ import annotations

import time
from datetime import date

import requests

BASE_URL = "https://www.tefas.gov.tr/api/funds"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
    "Accept": "application/json",
}

# YAT = mutual funds, EMK = pension, BYF = ETFs, GYF = REIFs, GSYF = VC funds
FUND_TYPES = ("YAT", "EMK", "BYF", "GYF", "GSYF")

PAGE_SIZE = 8000


class TefasError(RuntimeError):
    pass


# TEFAS signals "this range has no rows" by throwing a Java error rather
# than returning an empty list. Matched narrowly on purpose: anything
# else must still surface as a real failure.
_EMPTY_RESULT_ERRORS = ("Index 0 out of bounds for length 0",)


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


def _post(session: requests.Session, endpoint: str, payload: dict,
          retries: int = 6) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.post(url, json=payload, headers=HEADERS, timeout=90)
            if resp.status_code == 429:
                # TEFAS rate limit: back off hard, honor Retry-After if sent
                wait = int(resp.headers.get("Retry-After") or 0) \
                    or 45 * (attempt + 1)
                print(f"  rate limited (429), sleeping {wait}s...")
                time.sleep(wait)
                last_err = TefasError("429 Too Many Requests")
                continue
            resp.raise_for_status()
            body = resp.json()
            if body.get("errorMessage"):
                msg = str(body["errorMessage"])
                if any(p in msg for p in _EMPTY_RESULT_ERRORS):
                    # TEFAS raises a server-side IndexOutOfBounds instead of
                    # returning an empty list when a range holds no fund
                    # data — e.g. a weekend or a multi-day bayram. That is
                    # "no rows", not a failure, and letting it propagate
                    # crashed the whole nightly run.
                    print(f"  {endpoint}: no data in range (TEFAS: {msg})")
                    return {"resultList": [], "toplamSayi": 0}
                raise TefasError(f"{endpoint}: {msg}")
            return body
        except (requests.RequestException, ValueError) as err:
            last_err = err
            time.sleep(2 ** attempt)
    raise TefasError(f"{endpoint} failed after {retries} attempts: {last_err}")


def _payload(start: date, end: date, fund_type: str, fund_code: str | None,
             bas_sira: int, bit_sira: int) -> dict:
    return {
        "fonTipi": fund_type,
        "fonKodu": fund_code.upper() if fund_code else None,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "basTarih": _fmt(start),
        "bitTarih": _fmt(end),
        "basSira": bas_sira,
        "bitSira": bit_sira,
        "fonTurAciklama": None,
        "dil": "TR",
        "kurucuKod": None,
    }


# Fields we depend on downstream. If TEFAS renames its response wrapper
# or a column, `.get()` would silently yield None and we'd ingest bad
# data — so we assert the contract and fail loudly, naming what changed.
_HISTORY_KEYS = {"fonKodu", "tarih", "fiyat", "tedPaySayisi",
                 "kisiSayisi", "portfoyBuyukluk"}


def _check_contract(body: dict, endpoint: str, required: set[str],
                    min_extra: int = 0) -> None:
    if "resultList" not in body:
        raise TefasError(
            f"{endpoint}: response has no 'resultList' key — the TEFAS API "
            f"shape likely changed. Top-level keys: {sorted(body)[:8]}")
    rows = body["resultList"] or []
    if not rows:
        return  # legitimately empty (e.g. a date range with no data)
    have = set(rows[0])
    missing = required - have
    if missing:
        raise TefasError(
            f"{endpoint}: rows are missing expected fields "
            f"{sorted(missing)} — TEFAS schema likely changed. "
            f"Got fields: {sorted(have)[:14]}")
    if len(have) < len(required) + min_extra:
        raise TefasError(
            f"{endpoint}: rows have only {len(have)} fields "
            f"(expected ≥ {len(required) + min_extra}) — allocation "
            f"columns may have been dropped. Got: {sorted(have)[:14]}")


def _fetch_paged(session: requests.Session, endpoint: str, start: date,
                 end: date, fund_type: str, fund_code: str | None,
                 required: set[str] | None = None,
                 min_extra: int = 0) -> list[dict]:
    rows: list[dict] = []
    bas = 1
    checked = False
    while True:
        body = _post(session, endpoint,
                     _payload(start, end, fund_type, fund_code,
                              bas, bas + PAGE_SIZE - 1))
        if not checked and required is not None:
            _check_contract(body, endpoint, required, min_extra)
            checked = True
        page = body.get("resultList") or []
        rows.extend(page)
        total = body.get("toplamSayi") or 0
        bas += PAGE_SIZE
        if bas > total or not page:
            break
    return rows


def fetch_history(session: requests.Session, start: date, end: date,
                  fund_type: str = "YAT",
                  fund_code: str | None = None) -> list[dict]:
    """Daily NAV records: fonKodu, fonUnvan, tarih (ISO), fiyat,
    tedPaySayisi, kisiSayisi, portfoyBuyukluk."""
    return _fetch_paged(session, "fonGnlBlgSiraliGetir",
                        start, end, fund_type, fund_code,
                        required=_HISTORY_KEYS)


def fetch_allocation(session: requests.Session, start: date, end: date,
                     fund_type: str = "YAT",
                     fund_code: str | None = None) -> list[dict]:
    """Daily portfolio weights: fonKodu, tarih plus ~55 lowercase
    asset-class percentage columns (hs=equity, dt=gov bond, ...)."""
    # require the anchors + at least ~10 asset columns present
    return _fetch_paged(session, "dagilimSiraliGetirT",
                        start, end, fund_type, fund_code,
                        required={"fonKodu", "tarih"}, min_extra=10)


def make_session() -> requests.Session:
    return requests.Session()
