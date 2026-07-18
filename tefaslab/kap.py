"""KAP fund holdings pipeline (see docs/KAP_HOLDINGS.md).

Three stages, all plain requests:
  1. scan   — walk sequential disclosure ids via the 9KB excel export,
              keep "Portföy Dağılım Raporu" hits (fund, year, period)
  2. parse  — fetch each hit's Bildirim page -> attachment objId ->
              download the PDF (strip the Java-serialization wrapper)
              -> reconstruct the SPK portfolio table from word
              positions -> fund_holdings rows
  3. query  — who owns a stock / what does a fund own

Enumeration is forward-only: history accumulates from the first scan.
"""

from __future__ import annotations

import io
import re
import sqlite3
import time
from datetime import date

import pdfplumber
import requests

from . import db

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

EXPORT = "https://www.kap.org.tr/tr/api/notification/export/excel/{}"
PAGE = "https://www.kap.org.tr/tr/Bildirim/{}"
FILE = "https://www.kap.org.tr/tr/api/file/download/{}"

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
PAUSE = 0.6

SCHEMA = """
CREATE TABLE IF NOT EXISTS kap_disclosures (
    id          INTEGER PRIMARY KEY,     -- KAP disclosure index
    fund_title  TEXT,
    code        TEXT,                    -- TEFAS fund code (once parsed)
    year        INTEGER,
    period      INTEGER,                 -- month number
    obj_id      TEXT,
    status      TEXT NOT NULL DEFAULT 'found'  -- found|parsed|error
);
CREATE TABLE IF NOT EXISTS fund_holdings (
    code        TEXT NOT NULL,
    period      TEXT NOT NULL,           -- YYYY-MM
    isin        TEXT NOT NULL,
    ticker      TEXT,
    name        TEXT,
    quantity    REAL,
    value       REAL,                    -- market value, TRY
    weight_pct  REAL,                    -- % of fund total value
    disclosure_id INTEGER,
    PRIMARY KEY (code, period, isin)
);
CREATE INDEX IF NOT EXISTS idx_holdings_isin ON fund_holdings(isin);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON fund_holdings(ticker);
"""


def _connect(db_path=db.DB_PATH) -> sqlite3.Connection:
    conn = db.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------- scan

def scan_range(conn: sqlite3.Connection, start: int, count: int,
               session: requests.Session | None = None) -> dict:
    """Fingerprint ids [start, start+count) via excel export."""
    s = session or requests.Session()
    found = empty = 0
    consecutive_empty = 0
    for did in range(start, start + count):
        if consecutive_empty >= 400:
            # long empty run = we've likely passed the current id
            # ceiling; stop instead of burning requests
            break
        if conn.execute("SELECT 1 FROM kap_disclosures WHERE id=?",
                        (did,)).fetchone():
            continue
        # the export endpoint intermittently returns empty bodies under
        # load — retry empties once with a longer pause
        r = None
        for attempt in range(2):
            try:
                r = s.get(EXPORT.format(did), headers=H, timeout=30)
            except requests.RequestException:
                time.sleep(3)
                continue
            if r.status_code == 200 and len(r.content) >= 500:
                break
            time.sleep(2.5)
        if r is None or r.status_code != 200 or len(r.content) < 500:
            empty += 1
            consecutive_empty += 1
            time.sleep(PAUSE)
            continue
        consecutive_empty = 0
        text = r.content.decode("utf-8", errors="ignore")
        if "Portföy Dağılım Raporu" in text:
            title = re.search(r"<h1[^>]*>([^<]+)</h1>", text)
            year = re.search(r"Yıl:\s*(\d{4})", text)
            per = re.search(r"Periyot:\s*(\d{1,2})", text)
            conn.execute(
                "INSERT OR IGNORE INTO kap_disclosures"
                "(id, fund_title, year, period) VALUES (?, ?, ?, ?)",
                (did, title.group(1).strip() if title else None,
                 int(year.group(1)) if year else None,
                 int(per.group(1)) if per else None))
            found += 1
        time.sleep(PAUSE)
    conn.commit()
    # remember the frontier for forward scanning
    hi = conn.execute("SELECT MAX(id) FROM kap_disclosures").fetchone()[0]
    return {"scanned": count, "found": found, "empty": empty,
            "max_id": hi}


# --------------------------------------------------------------- parse

def _extract_pdf(raw: bytes) -> bytes:
    i = raw.find(b"%PDF")
    if i < 0:
        raise ValueError("no %PDF marker in download")
    return raw[i:]


def _num(s: str, dec: str = ".") -> float | None:
    """Parse a number in the document's detected format. Turkish PDFs use
    '.' for thousands and ',' for decimal (1.234.567,89); others are the
    reverse. Getting this wrong turns '1,47' into 147."""
    if not re.search(r"\d", s):
        return None
    if dec == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _detect_decimal(text: str) -> str:
    """Infer the decimal separator for the whole document. Prefer the
    unambiguous grouped forms (1.234.567,89 vs 1,234,567.89); else fall
    back to whichever 2-decimal form is more common."""
    tr = len(re.findall(r"\d{1,3}(?:\.\d{3})+,\d+", text))
    us = len(re.findall(r"\d{1,3}(?:,\d{3})+\.\d+", text))
    if tr or us:
        return "," if tr >= us else "."
    tr2 = len(re.findall(r"\d+,\d{2}\b", text))
    us2 = len(re.findall(r"\d+\.\d{2}\b", text))
    return "," if tr2 > us2 else "."


def _header_x(words, sub: str) -> float | None:
    return next((w["x0"] for w in words if sub in w["text"].upper()), None)


def parse_pdf_holdings(pdf_bytes: bytes) -> tuple[str | None, list[dict]]:
    """Reconstruct the FON PORTFÖY DEĞERİ TABLOSU from word positions.

    Rows are ISIN-anchored. The numeric columns live at issuer-specific
    x-positions and in either number format, so instead of hardcoding
    coordinates we (a) detect the document's decimal separator and (b)
    locate the right-hand value/weight cluster from the '(FPD GÖRE)' /
    '(FTD GÖRE)' column headers — the standard SPK labels for a holding's
    share of the fund. Weight is the rightmost percentage column (Toplam
    Değere göre); the largest number in the cluster is the total value.
    Wrapped names push the numbers onto a neighbouring visual line, which
    is re-attached to the nearest unmatched ISIN line by vertical
    distance.
    """
    holdings: list[dict] = []
    fund_code = None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        all_text = " ".join(w["text"] for p in pdf.pages
                            for w in p.extract_words())
        dec = _detect_decimal(all_text)
        width = pdf.pages[0].width
        first_text = pdf.pages[0].extract_text() or ""
        m = re.search(r"\b([A-Z0-9]{2,5})\s*-\s*[A-ZÇĞİÖŞÜ]", first_text)
        if m:
            fund_code = m.group(1)
        # Locate the value/weight cluster from the SPK column headers. The
        # threshold sits just left of the total-value column so the money
        # value and the trailing % columns are captured, nothing to their
        # left. Falls back to a width fraction if the headers are absent.
        hw = pdf.pages[0].extract_words()
        fpd = _header_x(hw, "(FPD")
        ftd = _header_x(hw, "(FTD")
        gap = (ftd - fpd) if (ftd and fpd and ftd > fpd) else width * 0.03
        vthresh = (fpd - 3.5 * gap) if fpd else width * 0.55
        for page in pdf.pages:
            words = page.extract_words()
            lines: dict[int, list] = {}
            for w in words:
                key = round(w["top"] / 3)
                lines.setdefault(key, []).append(w)
            isin_rows, value_rows = [], []
            for key in sorted(lines):
                ws = sorted(lines[key], key=lambda w: w["x0"])
                has_isin = any(ISIN_RE.match(t["text"]) for t in ws)
                has_values = any(w["x0"] > vthresh
                                 and _num(w["text"], dec) is not None
                                 for w in ws)
                if has_isin:
                    isin_rows.append({"top": key * 3, "words": ws,
                                      "matched": has_values})
                elif has_values and not any(w["x0"] < 100 for w in ws):
                    value_rows.append({"top": key * 3, "words": ws,
                                       "used": False})
            # attach orphan value lines to nearest unmatched ISIN line
            for row in isin_rows:
                if row["matched"]:
                    continue
                best = None
                for vr in value_rows:
                    if vr["used"]:
                        continue
                    d = abs(vr["top"] - row["top"])
                    if d < 40 and (best is None or d < best[0]):
                        best = (d, vr)
                if best:
                    best[1]["used"] = True
                    row["words"] = row["words"] + best[1]["words"]
            for row in isin_rows:
                ws = sorted(row["words"], key=lambda w: w["x0"])
                isin = next((w["text"] for w in ws
                             if ISIN_RE.match(w["text"])), None)
                if not isin:
                    continue
                ticker = (ws[0]["text"] if ws[0]["x0"] < 60
                          and not ISIN_RE.match(ws[0]["text"]) else None)
                isin_x = next(w["x0"] for w in ws if w["text"] == isin)
                name = " ".join(
                    w["text"] for w in ws
                    if 60 < w["x0"] < isin_x and w["text"] != "TL"
                    and not ISIN_RE.match(w["text"])
                    and _num(w["text"], dec) is None
                    and not re.match(r"\d", w["text"]))
                nums_mid = [_num(w["text"], dec) for w in ws
                            if isin_x < w["x0"] < vthresh
                            and _num(w["text"], dec) is not None]
                nums_val = [(w["x0"], _num(w["text"], dec)) for w in ws
                            if w["x0"] > vthresh
                            and _num(w["text"], dec) is not None]
                quantity = nums_mid[0] if nums_mid else None
                value = weight = None
                if nums_val:
                    nums_val.sort()
                    value = max(v for _, v in nums_val)
                    weight = nums_val[-1][1]
                    if weight is not None and weight > 100:
                        weight = None
                holdings.append({"isin": isin, "ticker": ticker,
                                 "name": name[:80] or None,
                                 "quantity": quantity, "value": value,
                                 "weight_pct": weight})
    return fund_code, holdings


def daily_update(conn: sqlite3.Connection, max_ids: int = 2500) -> dict:
    """Pipeline stage: scan forward from the id frontier, then parse.
    Stops early after 400 consecutive empty ids (past the ceiling)."""
    conn.executescript(SCHEMA)
    hi = conn.execute("SELECT MAX(id) FROM kap_disclosures").fetchone()[0]
    if hi is None:
        print("  no kap frontier yet — run `holdings scan` once first")
        return {}
    out = scan_range(conn, hi + 1, max_ids)
    out.update(parse_pending(conn, limit=300))
    return out


def reparse(conn: sqlite3.Connection, limit: int = 500,
            session: requests.Session | None = None) -> dict:
    """Re-download and re-parse every already-processed disclosure with
    the CURRENT parser — e.g. after a parser fix that recovers columns
    the old one dropped. Resets 'parsed'/'error' rows to 'found' so
    parse_pending picks them up; INSERT OR REPLACE overwrites the stale
    fund_holdings rows, so it is idempotent and safe to re-run."""
    conn.executescript(SCHEMA)
    n = conn.execute(
        "UPDATE kap_disclosures SET status='found' "
        "WHERE status IN ('parsed', 'error')").rowcount
    conn.commit()
    print(f"  reset {n} disclosures to 'found' for reparse")
    return parse_pending(conn, limit=limit, session=session)


def _fetch_disclosure(s: requests.Session, did: int,
                      retries: int = 3) -> tuple[str, bytes]:
    """Resolve a disclosure's attachment objId and download its PDF,
    retrying the transient KAP failures — empty / no-objId page, non-PDF
    body — that spike when many ids are fetched in a burst (a rate limit
    shows up as a whole contiguous block of 'no %PDF marker' errors)."""
    last = "download failed"
    for attempt in range(retries):
        try:
            page = s.get(PAGE.format(did), headers=H, timeout=60).text
            objs = re.findall(r'objId\\":\\"([0-9a-f]{32})', page)
            if not objs:
                last = "no attachment objId on page"
            else:
                raw = s.get(FILE.format(objs[0]), headers=H,
                            timeout=120).content
                if raw.find(b"%PDF") >= 0:
                    return objs[0], _extract_pdf(raw)
                last = "no %PDF marker in download"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(3 * (attempt + 1))
    raise ValueError(last)


def parse_pending(conn: sqlite3.Connection, limit: int = 50,
                  session: requests.Session | None = None) -> dict:
    """Resolve + parse disclosures in status 'found'."""
    s = session or requests.Session()
    known_codes = {c for (c,) in conn.execute("SELECT code FROM funds")}
    titles = {t: c for c, t in conn.execute(
        "SELECT code, title FROM funds") if t}
    rows = conn.execute(
        "SELECT id, fund_title, year, period FROM kap_disclosures "
        "WHERE status='found' ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    ok = err = 0
    for did, fund_title, year, per in rows:
        try:
            obj_id, pdf = _fetch_disclosure(s, did)
            code, holdings = parse_pdf_holdings(pdf)
            if code not in known_codes:
                code = titles.get(fund_title)
            if not code:
                raise ValueError(f"fund code unresolved ({fund_title!r})")
            if not holdings:
                raise ValueError("no ISIN rows parsed")
            if len(holdings) > 600:
                # a recognized template never yields this many rows; the
                # parser tripped on an unfamiliar layout (e.g. GZR's
                # narrow form) — don't write garbage, fail loudly instead.
                raise ValueError(f"implausible holding count "
                                 f"{len(holdings)} — template not recognized")
            period = (f"{year}-{per:02d}" if year and per
                      else f"{date.today():%Y-%m}")
            conn.executemany(
                "INSERT OR REPLACE INTO fund_holdings"
                "(code, period, isin, ticker, name, quantity, value, "
                "weight_pct, disclosure_id) VALUES (?,?,?,?,?,?,?,?,?)",
                [(code, period, h["isin"], h["ticker"], h["name"],
                  h["quantity"], h["value"], h["weight_pct"], did)
                 for h in holdings])
            conn.execute("UPDATE kap_disclosures SET status='parsed', "
                         "code=?, obj_id=? WHERE id=?",
                         (code, obj_id, did))
            ok += 1
            print(f"  {did} {code}: {len(holdings)} holdings ({period})")
        except Exception as e:
            conn.execute("UPDATE kap_disclosures SET status='error' "
                         "WHERE id=?", (did,))
            err += 1
            print(f"  {did} ERROR: {e}")
        conn.commit()
        time.sleep(PAUSE)
    return {"parsed": ok, "errors": err}


# --------------------------------------------------------------- query

def who_owns(conn: sqlite3.Connection, ticker: str):
    import pandas as pd
    return pd.read_sql_query(
        """
        SELECT h.code, f.title, h.period, h.weight_pct, h.value / 1e6
               AS value_mn
        FROM fund_holdings h LEFT JOIN funds f ON f.code = h.code
        WHERE h.ticker = ? AND h.period =
              (SELECT MAX(period) FROM fund_holdings)
        ORDER BY h.weight_pct DESC
        """, conn, params=(ticker.upper(),))


def fund_book(conn: sqlite3.Connection, code: str):
    import pandas as pd
    return pd.read_sql_query(
        """
        SELECT period, ticker, isin, name, quantity, value / 1e6
               AS value_mn, weight_pct
        FROM fund_holdings WHERE code = ? AND period =
              (SELECT MAX(period) FROM fund_holdings WHERE code = ?)
        ORDER BY weight_pct DESC
        """, conn, params=(code.upper(), code.upper()))
