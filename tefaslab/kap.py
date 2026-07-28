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
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from collections import defaultdict
from datetime import date, timedelta

import pdfplumber
import requests

from . import db
from . import mkk

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

EXPORT = "https://www.kap.org.tr/tr/api/notification/export/excel/{}"
PAGE = "https://www.kap.org.tr/tr/Bildirim/{}"
FILE = "https://www.kap.org.tr/tr/api/file/download/{}"

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
PAUSE = 0.6
# Empty KAP ids are normal; waiting 30 seconds twice for each one made a
# bounded backfill crawl at only ~250 ids per run. Keep enough time for a
# legitimate response, retry only ambiguous/transient responses once, and let
# the persisted cursor revisit what remains later.
EXPORT_TIMEOUT = 12
EQUITY_ORIENTED_CATEGORIES = (
    "Equity Turkey", "Foreign Equity", "Mixed", "Variable",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS kap_disclosures (
    id          INTEGER PRIMARY KEY,     -- KAP disclosure index
    fund_title  TEXT,
    code        TEXT,                    -- TEFAS fund code (once parsed)
    year        INTEGER,
    period      INTEGER,                 -- month number
    obj_id      TEXT,
    status      TEXT NOT NULL DEFAULT 'found', -- found|retry|parsed|error
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    last_attempt_at TEXT
);
CREATE TABLE IF NOT EXISTS kap_fund_aliases (
    kap_title   TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    note        TEXT
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
    source      TEXT NOT NULL DEFAULT 'kap-public',
    attachment_id TEXT,
    attachment_sha256 TEXT,
    parser_version TEXT,
    published_at TEXT,
    PRIMARY KEY (code, period, isin)
);
CREATE INDEX IF NOT EXISTS idx_holdings_isin ON fund_holdings(isin);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON fund_holdings(ticker);
-- Where the forward scan has reached. Kept SEPARATE from MAX(disclosure
-- id) on purpose: anchoring the scan to the last *found* report meant the
-- cursor stopped advancing whenever a window held no fund report, and it
-- rescanned the same ids nightly forever while KAP moved thousands of ids
-- ahead. This cursor advances on every scan.
CREATE TABLE IF NOT EXISTS kap_scan_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cursor      INTEGER NOT NULL,
    updated_at  TEXT
);
-- Separate cursor walking DOWN from the earliest known disclosure, to
-- recover periods from before coverage began. KAP ids are chronological,
-- so each older monthly filing cluster sits some way below the current
-- floor; this finds them the same way the forward scan finds new ones.
-- (Own table rather than a second row: kap_scan_state is CHECK(id = 1).)
CREATE TABLE IF NOT EXISTS kap_backfill_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cursor      INTEGER NOT NULL,   -- lowest id scanned so far
    updated_at  TEXT
);
-- One row per in-scope fund for each monthly reporting period that has
-- passed its publication grace window.  This is deliberately a coverage
-- ledger, not an assertion that an unseen fund has no holdings or failed to
-- publish: KAP discovery is imperfect, so `unseen` means exactly that.
CREATE TABLE IF NOT EXISTS kap_monthly_status (
    period      TEXT NOT NULL,           -- YYYY-MM, portfolio month
    code        TEXT NOT NULL,
    state       TEXT NOT NULL,           -- parsed|pending|error|unseen
    disclosure_id INTEGER,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (period, code)
);
CREATE INDEX IF NOT EXISTS idx_kap_monthly_status_period
    ON kap_monthly_status(period, state);
-- Official MKK index and immutable provenance.  MKK disclosure indexes are
-- not assumed to be interchangeable with KAP's public notification ids.
CREATE TABLE IF NOT EXISTS mkk_funds (
    code        TEXT PRIMARY KEY,
    fund_id     TEXT,
    title       TEXT,
    fund_type   TEXT,
    fund_class  TEXT,
    fund_state  TEXT,
    kap_url     TEXT,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mkk_disclosures (
    disclosure_index INTEGER PRIMARY KEY,
    fund_code   TEXT,
    fund_id     TEXT,
    title       TEXT,
    sub_report_ids TEXT,
    accepted_file_types TEXT,
    subject     TEXT,
    reporting_period TEXT,
    published_at TEXT,
    attachment_urls TEXT,
    detail_json TEXT,
    status      TEXT NOT NULL DEFAULT 'indexed',
                -- indexed|ignored|found|parsed|error
    attempts    INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT,
    checked_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mkk_disclosures_status
    ON mkk_disclosures(status, disclosure_index);
CREATE INDEX IF NOT EXISTS idx_mkk_disclosures_period
    ON mkk_disclosures(fund_code, reporting_period, disclosure_index);
CREATE TABLE IF NOT EXISTS mkk_scan_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cursor      INTEGER NOT NULL,
    last_index  INTEGER,
    updated_at  TEXT NOT NULL
);
"""

MAX_RETRY_ATTEMPTS = 3


def _connect(db_path=db.DB_PATH) -> sqlite3.Connection:
    conn = db.connect(db_path)
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply additive KAP-ledger migrations to cached pre-existing DBs."""
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(kap_disclosures)")}
    for name, definition in (
        ("attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("last_error", "TEXT"),
        ("last_attempt_at", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE kap_disclosures ADD COLUMN {name} {definition}")
    holding_columns = {row[1] for row in conn.execute("PRAGMA table_info(fund_holdings)")}
    for name, definition in (
        ("source", "TEXT NOT NULL DEFAULT 'kap-public'"),
        ("attachment_id", "TEXT"),
        ("attachment_sha256", "TEXT"),
        ("parser_version", "TEXT"),
        ("published_at", "TEXT"),
    ):
        if name not in holding_columns:
            conn.execute(f"ALTER TABLE fund_holdings ADD COLUMN {name} {definition}")
    conn.commit()


def _normalise_title(value: str | None) -> str:
    """Canonicalise Turkish fund titles for exact, non-fuzzy matching."""
    value = (value or "").upper().translate(str.maketrans({
        "Ç": "C", "Ğ": "G", "İ": "I", "I": "I", "Ö": "O",
        "Ş": "S", "Ü": "U", "Â": "A", "Î": "I", "Û": "U",
    }))
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if ch.isascii() and ch.isalnum())


def set_title_alias(conn: sqlite3.Connection, kap_title: str, code: str,
                    note: str | None = None) -> None:
    """Store an operator-reviewed KAP-title to TEFAS-code mapping."""
    _ensure_schema(conn)
    valid = conn.execute("SELECT 1 FROM funds WHERE code=?", (code.upper(),)).fetchone()
    if not valid:
        raise ValueError(f"unknown fund code: {code}")
    conn.execute(
        "INSERT INTO kap_fund_aliases (kap_title, code, note) VALUES (?,?,?) "
        "ON CONFLICT(kap_title) DO UPDATE SET code=excluded.code, note=excluded.note",
        (kap_title.strip(), code.upper(), note),
    )
    conn.commit()


# ---------------------------------------------------------------- scan

def _fetch_export(s: requests.Session, did: int):
    """Fetch one cheap KAP export without spending the scan on known empties.

    Returns the last response (or ``None``) plus the number of retry attempts.
    A 404/410 is a normal absent disclosure and is never retried. Empty 200s,
    throttles and server errors get one short retry because KAP intermittently
    serves a blank body for a real disclosure.
    """
    last = None
    retries = 0
    for attempt in range(2):
        try:
            last = s.get(EXPORT.format(did), headers=H, timeout=EXPORT_TIMEOUT)
        except requests.RequestException:
            if attempt == 0:
                retries += 1
                time.sleep(1.5)
                continue
            return None, retries
        if last.status_code == 200 and len(last.content) >= 500:
            return last, retries
        if last.status_code in (404, 410):
            return last, retries
        if attempt == 0:
            retries += 1
            time.sleep(1.5 if last.status_code == 200 else 2.5)
    return last, retries

def scan_range(conn: sqlite3.Connection, start: int, count: int,
               session: requests.Session | None = None,
               max_seconds: float | None = None,
               descending: bool = False) -> dict:
    """Fingerprint ids [start, start+count) via excel export.

    max_seconds bounds the wall clock: per-id cost is not ours to control
    (KAP throttles, and a throttled fetch costs two 30s timeouts), so a
    plain id count is an unbounded amount of work — one run ground on for
    9h and starved the nightly pipeline behind the concurrency lock.
    Callers persist a cursor, so stopping early just means resuming later.

    descending walks the block high->low, which keeps the scanned region
    contiguous when a backfill stops early.
    """
    s = session or requests.Session()
    found = empty = transient_retries = 0
    consecutive_empty = 0
    t0 = time.time()
    scanned = 0
    last_scanned = start + count - 1 if descending else start
    # highest id seen to actually exist — this is KAP's live ceiling, and
    # what the forward cursor should resume from next run
    last_content = start - 1
    ids = range(start, start + count)
    for did in (reversed(ids) if descending else ids):
        if max_seconds and time.time() - t0 > max_seconds:
            print(f"  time budget hit after {scanned} ids "
                  f"({time.time() - t0:.0f}s) — stopping, cursor persists")
            break
        if consecutive_empty >= 400:
            # long empty run = we've likely passed the current id
            # ceiling; stop instead of burning requests
            break
        last_scanned = did
        scanned += 1
        if scanned % 250 == 0:
            print(f"    ...{scanned}/{count} ids, {found} found, "
                  f"{time.time() - t0:.0f}s elapsed")
        if conn.execute("SELECT 1 FROM kap_disclosures WHERE id=?",
                        (did,)).fetchone():
            last_content = did          # known report: the id exists
            continue
        # the export endpoint intermittently returns empty bodies under
        # load — retry empties once with a longer pause
        r, retries = _fetch_export(s, did)
        transient_retries += retries
        if r is None or r.status_code != 200 or len(r.content) < 500:
            empty += 1
            consecutive_empty += 1
            time.sleep(PAUSE)
            continue
        consecutive_empty = 0
        last_content = did
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
    return {"scanned": scanned, "found": found, "empty": empty,
            "transient_retries": transient_retries,
            "max_id": hi, "last_content": last_content,
            "last_scanned": last_scanned,
            "seconds": round(time.time() - t0)}


def _get_cursor(conn: sqlite3.Connection) -> int:
    """Where the forward scan resumes. Seeds from the highest known
    disclosure id the first time, then moves independently."""
    row = conn.execute("SELECT cursor FROM kap_scan_state WHERE id=1").fetchone()
    if row:
        return int(row[0])
    hi = conn.execute("SELECT MAX(id) FROM kap_disclosures").fetchone()[0]
    return int(hi or 0)


def _set_cursor(conn: sqlite3.Connection, value: int) -> None:
    conn.execute(
        "INSERT INTO kap_scan_state (id, cursor, updated_at) "
        "VALUES (1, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET cursor=excluded.cursor, "
        "updated_at=excluded.updated_at", (int(value),))
    conn.commit()


def scan_forward(conn: sqlite3.Connection, budget: int = 4000,
                 session: requests.Session | None = None,
                 max_seconds: float = 1500) -> dict:
    """Scan the next `budget` ids from the persisted cursor and advance
    it — whether or not anything was found.

    KAP mints ids for every filing market-wide (thousands a day), so fund
    portfolio reports sit in sparse clusters. The old scan restarted at
    MAX(found id) each night, so a window with no fund report left the
    cursor parked and the same ids were refetched forever. Advancing the
    cursor lets the scan walk to KAP's live ceiling, picking up each
    month's reports as it passes them, then simply track the ceiling.
    """
    _ensure_schema(conn)
    start = _get_cursor(conn) + 1
    if start <= 1:
        print("  no kap frontier yet — run `holdings scan --start <id>` once")
        return {}
    out = scan_range(conn, start, budget, session,
                     max_seconds=max_seconds)
    # resume from the last id proven to exist; if the whole window was
    # empty we've run past the ceiling, so hold position and retry later.
    reached = max(out.get("last_content") or 0, start - 1)
    _set_cursor(conn, reached)
    out.update({"cursor_from": start, "cursor_to": reached,
                "advanced": reached - (start - 1)})
    print(f"  kap scan {start}..{start + budget - 1}: "
          f"found {out.get('found', 0)}, cursor -> {reached}")
    return out


def _get_back_cursor(conn: sqlite3.Connection) -> int:
    """Lowest id the backfill has scanned. Seeds from the earliest known
    disclosure, then walks down."""
    row = conn.execute(
        "SELECT cursor FROM kap_backfill_state WHERE id=1").fetchone()
    if row:
        return int(row[0])
    lo = conn.execute("SELECT MIN(id) FROM kap_disclosures").fetchone()[0]
    return int(lo or 0)


def _set_back_cursor(conn: sqlite3.Connection, value: int) -> None:
    conn.execute(
        "INSERT INTO kap_backfill_state (id, cursor, updated_at) "
        "VALUES (1, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET cursor=excluded.cursor, "
        "updated_at=excluded.updated_at", (int(value),))
    conn.commit()


def scan_backward(conn: sqlite3.Connection, budget: int = 4000,
                  session: requests.Session | None = None,
                  max_seconds: float = 1500) -> dict:
    """Walk DOWN from the earliest known disclosure to recover history.

    Holdings have been forward-only: coverage started wherever the first
    scan happened to begin, so everything filed before that is simply
    absent. Older monthly clusters bunch tightly on filing days, so this
    scans the block contiguously rather than trying to guess where they
    sit — clusters are found by walking past them.
    """
    _ensure_schema(conn)
    hi = _get_back_cursor(conn)
    if hi <= 1:
        print("  no kap floor yet — run `holdings scan --start <id>` once")
        return {}
    start = max(hi - budget, 1)
    # Walk high->low so that stopping early still leaves everything above
    # the new floor scanned; the floor is where we actually reached, not
    # where we hoped to.
    out = scan_range(conn, start, hi - start, session,
                     max_seconds=max_seconds, descending=True)
    floor = int(out.get("last_scanned", start))
    _set_back_cursor(conn, floor)
    out.update({"backfill_from": hi, "backfill_to": floor})
    print(f"  kap backfill {hi - 1}..{floor}: found {out.get('found', 0)} "
          f"in {out.get('seconds', 0)}s, floor -> {floor}")
    out.update(parse_pending(conn, limit=300, session=session))
    return out


def coverage_summary(conn: sqlite3.Connection) -> dict:
    """Classify the fund universe by its usable KAP-holdings state.

    A missing book has several materially different causes: KAP may not have
    been linked to the fund, a report can be waiting for download, or a PDF
    template can have failed parsing.  Keep those causes separate so neither
    the website nor operations treats every absence as a zero holding.

    Categories are mutually exclusive, in this order: parsed book, linked
    pending report, linked parser error, then no resolved KAP report.
    """
    _ensure_schema(conn)
    row = conn.execute("""
        WITH universe AS (
            SELECT code FROM funds
        ), parsed AS (
            SELECT DISTINCT code FROM fund_holdings WHERE code IS NOT NULL
        ), linked_reports AS (
            SELECT COALESCE(k.code, f.code) AS code,
                   MAX(CASE WHEN k.status IN ('found', 'retry') THEN 1 ELSE 0 END) AS pending,
                   MAX(CASE WHEN k.status = 'error' THEN 1 ELSE 0 END) AS errors
            FROM kap_disclosures k
            LEFT JOIN funds f ON f.title = k.fund_title
            WHERE COALESCE(k.code, f.code) IS NOT NULL
            GROUP BY COALESCE(k.code, f.code)
        )
        SELECT
            COUNT(*) AS universe,
            SUM(CASE WHEN p.code IS NOT NULL THEN 1 ELSE 0 END) AS parsed_funds,
            SUM(CASE WHEN p.code IS NULL AND r.pending = 1 THEN 1 ELSE 0 END)
                AS pending_funds,
            SUM(CASE WHEN p.code IS NULL AND COALESCE(r.pending, 0) = 0
                      AND r.errors = 1 THEN 1 ELSE 0 END) AS error_funds,
            SUM(CASE WHEN p.code IS NULL AND r.code IS NULL THEN 1 ELSE 0 END)
                AS no_resolved_report
        FROM universe u
        LEFT JOIN parsed p ON p.code = u.code
        LEFT JOIN linked_reports r ON r.code = u.code
    """).fetchone()
    reports = conn.execute("""
        SELECT
            SUM(CASE WHEN status = 'parsed' THEN 1 ELSE 0 END) AS parsed,
            SUM(CASE WHEN status IN ('found', 'retry') THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
            SUM(CASE WHEN code IS NULL AND NOT EXISTS (
                    SELECT 1 FROM funds f WHERE f.title = kap_disclosures.fund_title
                ) THEN 1 ELSE 0 END) AS unlinked
        FROM kap_disclosures
    """).fetchone()
    latest = conn.execute(
        "SELECT MAX(period) FROM fund_holdings").fetchone()[0]
    marks = ",".join("?" for _ in EQUITY_ORIENTED_CATEGORIES)
    equity = conn.execute(
        f"SELECT COUNT(*) AS universe, "
        f"SUM(CASE WHEN h.code IS NOT NULL THEN 1 ELSE 0 END) AS parsed "
        f"FROM funds f LEFT JOIN (SELECT DISTINCT code FROM fund_holdings) h "
        f"ON h.code=f.code WHERE f.category IN ({marks})",
        EQUITY_ORIENTED_CATEGORIES,
    ).fetchone()

    def n(value) -> int:
        return int(value or 0)

    return {
        "universe": n(row[0]),
        "parsed_funds": n(row[1]),
        "pending_funds": n(row[2]),
        "error_funds": n(row[3]),
        "no_resolved_report": n(row[4]),
        "parsed_reports": n(reports[0]),
        "pending_reports": n(reports[1]),
        "error_reports": n(reports[2]),
        "unlinked_reports": n(reports[3]),
        "latest_period": latest,
        "equity_oriented_universe": n(equity[0]),
        "equity_oriented_parsed": n(equity[1]),
    }


# ---------------------------------------------------------- MKK discovery

MKK_BATCH_SIZE = 50
MKK_PARSER_VERSION = "mkk-pdf-v1"


def _mkk_period(value: object) -> str | None:
    """Normalise a disclosure reporting period to ``YYYY-MM`` when explicit.

    MKK returns this field in different shapes for different disclosure
    templates.  We only infer a period from an unambiguous ISO/Turkish date;
    an absent or ambiguous period stays unresolved rather than being silently
    assigned to the month when the notification happened to be collected.
    """
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    match = re.search(r"\b((?:19|20)\d{2})[-/.]([01]?\d)\b", text)
    if match and 1 <= int(match.group(2)) <= 12:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    dates = re.findall(r"\b([0-3]?\d)[./-]([01]?\d)[./-]((?:19|20)\d{2})\b", text)
    if dates:
        # A period range's end date is the reporting month; a single date is
        # also a much stronger signal than the collection timestamp.
        day, month, year = dates[-1]
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{int(year):04d}-{int(month):02d}"
    return None


def _mkk_is_portfolio_report(summary: dict, detail: dict) -> bool:
    """Identify only explicit portfolio-distribution disclosures.

    A FON disclosure includes issuance documents, material events and many
    other report types.  Classification intentionally errs on the side of
    leaving an item uncollected: a false positive can overwrite a fund's
    monthly holdings snapshot.
    """
    text = " ".join([
        str(summary.get("title") or ""),
        mkk.subject_text(detail),
        str(detail.get("disclosureReason") or ""),
        " ".join(str(x) for x in summary.get("subReportIds") or []),
    ])
    folded = unicodedata.normalize("NFKD", text.casefold().replace("ı", "i"))
    folded = "".join(ch for ch in folded if ch.isascii())
    return any(token in folded for token in (
        "portfoy dagilim raporu", "portfolio distribution report",
        "portfolio distribution",
    ))


def sync_mkk_funds(conn: sqlite3.Connection, client: mkk.MKKClient | None = None) -> dict:
    """Checkpoint the official MKK fund registry without changing TEFAS data."""
    _ensure_schema(conn)
    client = client or mkk.MKKClient()
    now = datetime_now_iso()
    rows = []
    for fund in client.funds():
        code = str(fund.get("fundCode") or "").upper().strip()
        if not code:
            continue
        rows.append((
            code, str(fund.get("fundId") or "") or None,
            fund.get("fundName"), fund.get("fundType"), fund.get("fundClass"),
            fund.get("fundState"), fund.get("kapUrl"), now,
        ))
    conn.executemany(
        "INSERT INTO mkk_funds(code, fund_id, title, fund_type, fund_class, "
        "fund_state, kap_url, fetched_at) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET fund_id=excluded.fund_id, "
        "title=excluded.title, fund_type=excluded.fund_type, "
        "fund_class=excluded.fund_class, fund_state=excluded.fund_state, "
        "kap_url=excluded.kap_url, fetched_at=excluded.fetched_at",
        rows,
    )
    conn.commit()
    return {"funds": len(rows)}


def _mkk_scan_cursor(conn: sqlite3.Connection, latest: int) -> int:
    row = conn.execute("SELECT cursor FROM mkk_scan_state WHERE id=1").fetchone()
    # Start at the first id of the live 50-item window. Subsequent runs pick
    # up strictly new ids, avoiding both KAP's old brute-force scan and a
    # repeat of the same MKK window.
    return int(row[0]) if row else max(1, latest - MKK_BATCH_SIZE + 1)


def _set_mkk_scan_cursor(conn: sqlite3.Connection, cursor: int, last_index: int) -> None:
    conn.execute(
        "INSERT INTO mkk_scan_state(id, cursor, last_index, updated_at) VALUES "
        "(1,?,?,?) ON CONFLICT(id) DO UPDATE SET cursor=excluded.cursor, "
        "last_index=excluded.last_index, updated_at=excluded.updated_at",
        (cursor, last_index, datetime_now_iso()),
    )
    conn.commit()


def discover_mkk_disclosures(conn: sqlite3.Connection, batches: int = 1,
                             detail_limit: int = 4,
                             client: mkk.MKKClient | None = None) -> dict:
    """Collect MKK index metadata and inspect a bounded number of fund notices.

    The service limit is six calls/minute. A run therefore makes one request
    for the head index, up to ``batches`` list calls, then only a few detail
    calls for fund notices. The checkpoint lets routine runs make steady
    forward progress without ever bursting through the provider's quota.
    """
    _ensure_schema(conn)
    if batches < 1 or detail_limit < 0:
        raise ValueError("batches must be >= 1 and detail_limit must be >= 0")
    client = client or mkk.MKKClient()
    latest = client.last_disclosure_index()
    cursor = _mkk_scan_cursor(conn, latest)
    listed = 0
    for _ in range(batches):
        if cursor > latest:
            break
        batch = client.disclosures(cursor)
        if not batch:
            break
        now = datetime_now_iso()
        rows = []
        for item in batch:
            did = int(item["disclosureIndex"])
            rows.append((
                did, str(item.get("fundCode") or "").upper() or None,
                str(item.get("fundId") or "") or None, item.get("title"),
                json.dumps(item.get("subReportIds") or [], ensure_ascii=False),
                json.dumps(item.get("acceptedDataFileTypes") or [], ensure_ascii=False),
                now,
            ))
        conn.executemany(
            "INSERT INTO mkk_disclosures(disclosure_index, fund_code, fund_id, title, "
            "sub_report_ids, accepted_file_types, checked_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(disclosure_index) DO UPDATE SET "
            "fund_code=excluded.fund_code, fund_id=excluded.fund_id, title=excluded.title, "
            "sub_report_ids=excluded.sub_report_ids, "
            "accepted_file_types=excluded.accepted_file_types, checked_at=excluded.checked_at",
            rows,
        )
        conn.commit()
        listed += len(rows)
        cursor = max(int(item["disclosureIndex"]) for item in batch) + 1
        if len(batch) < MKK_BATCH_SIZE:
            break
    _set_mkk_scan_cursor(conn, cursor, latest)

    # Detail requests are the authoritative report classifier. Limit them
    # independently: list metadata does not reliably expose the Turkish
    # subject, and non-report fund disclosures must never be parsed as books.
    candidates = conn.execute(
        "SELECT disclosure_index, fund_code, fund_id, title, sub_report_ids "
        "FROM mkk_disclosures WHERE status='indexed' AND fund_code IS NOT NULL "
        "ORDER BY disclosure_index DESC LIMIT ?", (detail_limit,)).fetchall()
    inspected = found = ignored = errors = 0
    for did, code, fund_id, title, sub_report_ids in candidates:
        try:
            detail = client.disclosure_detail(int(did))
            attachment_urls = detail.get("attachmentUrls") or []
            summary = {"title": title, "subReportIds": json.loads(sub_report_ids or "[]")}
            is_report = _mkk_is_portfolio_report(summary, detail)
            period = _mkk_period(detail.get("period"))
            status = "found" if is_report else "ignored"
            conn.execute(
                "UPDATE mkk_disclosures SET subject=?, reporting_period=?, published_at=?, "
                "attachment_urls=?, detail_json=?, status=?, checked_at=?, last_error=NULL "
                "WHERE disclosure_index=?",
                (mkk.subject_text(detail), period, detail.get("time"),
                 json.dumps(attachment_urls, ensure_ascii=False),
                 json.dumps(detail, ensure_ascii=False), status, datetime_now_iso(), did),
            )
            found += int(is_report)
            ignored += int(not is_report)
        except Exception as exc:
            conn.execute(
                "UPDATE mkk_disclosures SET status='error', last_error=?, checked_at=? "
                "WHERE disclosure_index=?",
                (str(exc)[:500], datetime_now_iso(), did),
            )
            errors += 1
        conn.commit()
        inspected += 1
    return {"latest_index": latest, "cursor": cursor, "listed": listed,
            "inspected": inspected, "portfolio_reports": found,
            "ignored": ignored, "errors": errors}


# ------------------------------------------------------ monthly coverage

# KAP fund profiles currently list the next monthly notification in the
# first 1–10 calendar days after month end. Day 15 leaves room for weekends,
# corrections and a normal operations delay without concealing a missed run
# for another month.
MONTHLY_PUBLICATION_GRACE_DAYS = 15


def latest_due_period(as_of: date | None = None,
                      grace_days: int = MONTHLY_PUBLICATION_GRACE_DAYS) -> str:
    """Return the newest portfolio month whose publication window has closed.

    A portfolio for month M is only considered due after the end of M plus a
    generous grace period.  This prevents the UI and monitors from calling a
    current-month report "missing" before managers have a reasonable chance
    to publish it.
    """
    as_of = as_of or date.today()
    first = as_of.replace(day=1)
    # Walk backwards from the prior month. The loop is intentionally tiny but
    # makes the month-end calculation correct across leap years and January.
    for _ in range(24):
        month_end = first - timedelta(days=1)
        if as_of >= month_end + timedelta(days=grace_days):
            return f"{month_end:%Y-%m}"
        first = month_end.replace(day=1)
    raise RuntimeError("could not determine a due holdings period")


def refresh_monthly_status(conn: sqlite3.Connection, period: str | None = None,
                           as_of: date | None = None) -> dict:
    """Materialise per-fund monthly disclosure states for the public product.

    The in-scope universe is intentionally limited to categories where a
    security-level portfolio is decision-useful.  `unseen` is an observability
    state: it means the KAP scanner has not deterministically linked a report,
    *not* that the manager disclosed zero positions or necessarily failed to
    file.  This distinction is central to a defensible coverage metric.
    """
    _ensure_schema(conn)
    period = period or latest_due_period(as_of)
    try:
        year, month = (int(part) for part in period.split("-", 1))
    except ValueError as err:
        raise ValueError("period must be YYYY-MM") from err
    if not 1 <= month <= 12:
        raise ValueError("period must be YYYY-MM")

    eligible = [row[0] for row in conn.execute(
        f"SELECT code FROM funds WHERE category IN ({','.join('?' for _ in EQUITY_ORIENTED_CATEGORIES)})",
        EQUITY_ORIENTED_CATEGORIES,
    )]
    parsed = {row[0] for row in conn.execute(
        "SELECT DISTINCT code FROM fund_holdings WHERE period=?", (period,))}
    reports: dict[str, tuple[int, str]] = {}
    for code, did, status in conn.execute(
        """
        SELECT COALESCE(k.code, f.code) AS code, k.id, k.status
        FROM kap_disclosures k
        LEFT JOIN funds f ON f.title = k.fund_title
        WHERE k.year=? AND k.period=?
          AND COALESCE(k.code, f.code) IS NOT NULL
        ORDER BY k.id DESC
        """, (year, month)):
        # Keep the newest deterministic report; a parsed book is resolved
        # from fund_holdings above, while pending beats a terminal error so a
        # later retry is never hidden behind an earlier parser failure.
        if code not in reports or status in ("found", "retry"):
            reports[code] = (int(did), str(status))

    # The official MKK route uses a different disclosure-index namespace from
    # KAP's public notification pages, but it represents the same coverage
    # state. Include discovered MKK reports here so a verified report waiting
    # for its attachment parser is honestly shown as `pending`, never
    # `unseen`. The current UI does not construct a link from disclosure_id.
    for code, did, status in conn.execute(
        "SELECT fund_code, disclosure_index, status FROM mkk_disclosures "
        "WHERE reporting_period=? AND status IN ('found', 'parsed', 'error') "
        "ORDER BY disclosure_index DESC", (period,)):
        mapped = "found" if status == "found" else str(status)
        if code not in reports or mapped == "found":
            reports[str(code)] = (int(did), mapped)

    now = datetime_now_iso()
    rows = []
    for code in eligible:
        did, status = reports.get(code, (None, "unseen"))
        state = ("parsed" if code in parsed else
                 "pending" if status in ("found", "retry") else
                 "error" if status == "error" else "unseen")
        rows.append((period, code, state, did, now))
    conn.execute("DELETE FROM kap_monthly_status WHERE period=?", (period,))
    conn.executemany(
        "INSERT INTO kap_monthly_status(period, code, state, disclosure_id, updated_at) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    return monthly_status_summary(conn, period)


def datetime_now_iso() -> str:
    """One local helper keeps the SQLite coverage snapshot timestamp uniform."""
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def monthly_status_summary(conn: sqlite3.Connection,
                           period: str | None = None) -> dict:
    """Return a compact monthly holdings SLA/coverage summary."""
    _ensure_schema(conn)
    period = period or latest_due_period()
    rows = conn.execute(
        "SELECT state, COUNT(*) FROM kap_monthly_status WHERE period=? GROUP BY state",
        (period,)).fetchall()
    counts = {state: int(n) for state, n in rows}
    eligible = sum(counts.values())
    latest = conn.execute("SELECT MAX(period) FROM fund_holdings").fetchone()[0]
    return {
        "period": period,
        "eligible_funds": eligible,
        "parsed_funds": counts.get("parsed", 0),
        "pending_funds": counts.get("pending", 0),
        "error_funds": counts.get("error", 0),
        "unseen_funds": counts.get("unseen", 0),
        "latest_parsed_period": latest,
        "capture_rate": round(100 * counts.get("parsed", 0) / eligible, 1)
        if eligible else None,
    }


# --------------------------------------------------------------- parse

def _resolve_fund_code(
    pdf_code: str | None,
    fund_title: str | None,
    known_codes: set[str],
    exact_titles: dict[str, str],
    normalised_titles: dict[str, set[str]],
    aliases: dict[str, str],
) -> str | None:
    """Resolve only deterministic code/title relationships.

    Title similarity is deliberately *not* used: a bad holdings assignment is
    worse than an uncovered fund.  Normalised titles are accepted only when
    they map to exactly one TEFAS code; all ambiguous cases need an explicit
    operator alias.
    """
    if pdf_code in known_codes:
        return pdf_code
    if fund_title in exact_titles:
        return exact_titles[fund_title]
    if fund_title in aliases:
        return aliases[fund_title]
    matches = normalised_titles.get(_normalise_title(fund_title), set())
    return next(iter(matches)) if len(matches) == 1 else None


def _is_transient_parse_error(err: Exception) -> bool:
    """Only network/download failures should automatically re-enter the queue."""
    text = str(err).lower()
    return isinstance(err, requests.RequestException) or any(
        marker in text for marker in (
            "download failed", "no attachment objid", "no %pdf marker",
            "timeout", "connection", "temporarily",
        )
    )

def _extract_pdf(raw: bytes) -> bytes:
    i = raw.find(b"%PDF")
    if i < 0:
        raise ValueError("no %PDF marker in download")
    return raw[i:]


def _num(s: str, dec: str = ".") -> float | None:
    """Parse a number in the document's detected format. Turkish PDFs use
    '.' for thousands and ',' for decimal (1.234.567,89); others are the
    reverse. Getting this wrong turns '1,47' into 147. Some templates
    suffix a literal '%' on the weight column ('0.02%')."""
    s = s.strip().rstrip("%").strip()
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
                ticker = (ws[0]["text"].split(".")[0] if ws[0]["x0"] < 60
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
    # Some templates (the portrait Garanti form) list each purchase lot
    # of a security on its own line — collapse them into one position per
    # ISIN, summing value/weight/quantity. A no-op for one-row-per-ISIN
    # templates.
    agg: dict = {}
    for h in holdings:
        k = h["isin"]
        if k in agg:
            a = agg[k]
            for f in ("value", "weight_pct", "quantity"):
                a[f] = (a[f] or 0) + (h[f] or 0)
        else:
            agg[k] = h
    return fund_code, list(agg.values())


def daily_update(conn: sqlite3.Connection, max_ids: int = 5000) -> dict:
    """Pipeline stage: advance the forward scan, then parse what it found.

    Budget is sized to outpace KAP's id issuance (a few thousand a day) so
    the cursor closes the gap to the live ceiling and then tracks it —
    which is what makes new monthly reports arrive on their own.
    """
    _ensure_schema(conn)
    if _get_cursor(conn) <= 0:
        print("  no kap frontier yet — run `holdings scan --start <id>` once")
        return {}
    out = scan_forward(conn, budget=max_ids)
    # Safely re-attempt pre-retry-ledger failures once. New failures carry a
    # reason and are retried automatically only when the download was transient.
    out["legacy_errors"] = requeue_legacy_errors(conn, limit=50)
    out.update(parse_pending(conn, limit=300))
    out["monthly_coverage"] = refresh_monthly_status(conn)
    return out


def collect_monthly(conn: sqlite3.Connection, period: str | None = None,
                    max_ids: int = 5000, mkk_batches: int = 12,
                    mkk_detail_limit: int = 30,
                    mkk_parse_limit: int = 4) -> dict:
    """Collect the latest monthly books through the official MKK index.

    The client spaces calls 10.5 seconds apart, respecting the product quota.
    The older KAP-ID scan is a recovery fallback only when credentials have
    not been installed yet.
    """
    _ensure_schema(conn)
    period = period or latest_due_period()
    try:
        client = mkk.MKKClient()
        out: dict = {}
        out["mkk"] = discover_mkk_disclosures(
            conn, batches=mkk_batches, detail_limit=mkk_detail_limit, client=client)
        out["mkk_parse"] = parse_mkk_pending(
            conn, limit=mkk_parse_limit, client=client)
        # Recover a modest number of reports found before the MKK migration,
        # but do not run a second discovery crawl in the normal path.
        out["legacy_parse"] = parse_pending(conn, limit=50, period=period)
        out["monthly_coverage"] = refresh_monthly_status(conn, period)
        print("  monthly holdings coverage:", out["monthly_coverage"])
        return out
    except mkk.MKKConfigurationError:
        # The public scanner keeps old installations working until the MKK
        # secrets are installed. It is deliberately not the normal path.
        pass
    if _get_cursor(conn) <= 0:
        raise RuntimeError("no KAP frontier yet — seed the scanner before monthly collection")
    out = scan_forward(conn, budget=max_ids)
    out.update(parse_pending(conn, limit=250, period=period))
    out["monthly_coverage"] = refresh_monthly_status(conn, period)
    print("  monthly holdings coverage:", out["monthly_coverage"])
    return out


def reparse(conn: sqlite3.Connection, limit: int = 500,
            session: requests.Session | None = None) -> dict:
    """Re-download and re-parse every already-processed disclosure with
    the CURRENT parser — e.g. after a parser fix that recovers columns
    the old one dropped. Resets 'parsed'/'error' rows to 'found' so
    parse_pending picks them up; INSERT OR REPLACE overwrites the stale
    fund_holdings rows, so it is idempotent and safe to re-run."""
    _ensure_schema(conn)
    n = conn.execute(
        "UPDATE kap_disclosures SET status='found', attempts=0, last_error=NULL "
        "WHERE status IN ('parsed', 'retry', 'error')").rowcount
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
                  session: requests.Session | None = None,
                  period: str | None = None) -> dict:
    """Resolve + parse newly found/retry disclosures, optionally for a month."""
    _ensure_schema(conn)
    s = session or requests.Session()
    known_codes = {c for (c,) in conn.execute("SELECT code FROM funds")}
    titles = {t: c for c, t in conn.execute(
        "SELECT code, title FROM funds") if t}
    normalised_titles: dict[str, set[str]] = defaultdict(set)
    for title, code in titles.items():
        normalised_titles[_normalise_title(title)].add(code)
    aliases = {title: code for title, code in conn.execute(
        "SELECT kap_title, code FROM kap_fund_aliases")}
    where = "WHERE status IN ('found', 'retry')"
    params: list[object] = []
    if period:
        try:
            year, month = (int(part) for part in period.split("-", 1))
        except ValueError as err:
            raise ValueError("period must be YYYY-MM") from err
        where += " AND year=? AND period=?"
        params.extend((year, month))
    params.append(limit)
    rows = conn.execute(
        "SELECT id, fund_title, year, period, attempts FROM kap_disclosures "
        f"{where} "
        "ORDER BY CASE status WHEN 'found' THEN 0 ELSE 1 END, id DESC LIMIT ?",
        params).fetchall()
    ok = retry = err = 0
    for did, fund_title, year, per, attempts in rows:
        attempts = int(attempts or 0) + 1
        conn.execute(
            "UPDATE kap_disclosures SET attempts=?, last_attempt_at=datetime('now') "
            "WHERE id=?", (attempts, did))
        conn.commit()
        try:
            obj_id, pdf = _fetch_disclosure(s, did)
            code, holdings = parse_pdf_holdings(pdf)
            code = _resolve_fund_code(
                code, fund_title, known_codes, titles, normalised_titles, aliases)
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
                         "code=?, obj_id=?, last_error=NULL WHERE id=?",
                         (code, obj_id, did))
            ok += 1
            print(f"  {did} {code}: {len(holdings)} holdings ({period})")
        except Exception as e:
            transient = _is_transient_parse_error(e)
            next_status = "retry" if transient and attempts < MAX_RETRY_ATTEMPTS else "error"
            conn.execute("UPDATE kap_disclosures SET status=?, last_error=? "
                         "WHERE id=?", (next_status, str(e)[:500], did))
            if next_status == "retry":
                retry += 1
                print(f"  {did} RETRY {attempts}/{MAX_RETRY_ATTEMPTS}: {e}")
            else:
                err += 1
                print(f"  {did} ERROR: {e}")
        conn.commit()
        time.sleep(PAUSE)
    return {"parsed": ok, "retries": retry, "errors": err}


def parse_mkk_pending(conn: sqlite3.Connection, limit: int = 2,
                      client: mkk.MKKClient | None = None) -> dict:
    """Parse official-MKK-discovered portfolio report attachments.

    The MKK index gives the authoritative fund code and notice metadata; the
    attachment remains the source document. A successful newer report replaces
    the fund's complete snapshot for that reporting month, which also makes a
    corrected/re-uploaded disclosure safe: removed positions cannot linger.
    """
    _ensure_schema(conn)
    if limit < 0:
        raise ValueError("limit must be >= 0")
    client = client or mkk.MKKClient()
    known_codes = {c for (c,) in conn.execute("SELECT code FROM funds")}
    rows = conn.execute(
        "SELECT disclosure_index, fund_code, reporting_period, published_at, "
        "attachment_urls, attempts FROM mkk_disclosures WHERE status='found' "
        "ORDER BY disclosure_index DESC LIMIT ?", (limit,)).fetchall()
    parsed = errors = 0
    for did, fund_code, period, published_at, attachment_urls, attempts in rows:
        attempts = int(attempts or 0) + 1
        conn.execute("UPDATE mkk_disclosures SET attempts=?, checked_at=? "
                     "WHERE disclosure_index=?", (attempts, datetime_now_iso(), did))
        conn.commit()
        try:
            if not fund_code or fund_code not in known_codes:
                raise ValueError(f"MKK fund code is not in the TEFAS universe ({fund_code!r})")
            if not period:
                raise ValueError("MKK disclosure has no unambiguous reporting period")
            attachments = json.loads(attachment_urls or "[]")
            if not isinstance(attachments, list) or not attachments:
                raise ValueError("MKK disclosure has no attachments")
            # A correction can carry multiple files. Prefer a PDF attachment,
            # but try every advertised attachment before declaring failure.
            last_error: Exception | None = None
            selected_id = digest = None
            holdings: list[dict] | None = None
            for attachment in attachments:
                url = str(attachment.get("url") or "")
                if not url:
                    continue
                try:
                    raw = client.download_attachment(url)
                    pdf = _extract_pdf(raw)
                    pdf_code, candidate = parse_pdf_holdings(pdf)
                    if pdf_code and pdf_code.upper() != fund_code.upper():
                        raise ValueError(f"PDF code {pdf_code} differs from MKK {fund_code}")
                    if not candidate:
                        raise ValueError("no ISIN rows parsed")
                    if len(candidate) > 600:
                        raise ValueError(f"implausible holding count {len(candidate)}")
                    selected_id = url.rstrip("/").rsplit("/", 1)[-1]
                    digest = hashlib.sha256(raw).hexdigest()
                    holdings = candidate
                    break
                except Exception as exc:  # retain final attachment diagnosis
                    last_error = exc
            if holdings is None or selected_id is None or digest is None:
                raise last_error or ValueError("no usable MKK attachment")
            # The canonical index is chronological. If the same fund/month has
            # a later parsed report, do not let an older pending copy overwrite
            # it on a later retry.
            newer = conn.execute(
                "SELECT 1 FROM mkk_disclosures WHERE fund_code=? "
                "AND reporting_period=? AND status='parsed' "
                "AND disclosure_index > ?", (fund_code, period, did)).fetchone()
            if newer:
                conn.execute("UPDATE mkk_disclosures SET status='ignored', last_error=?, "
                             "checked_at=? WHERE disclosure_index=?",
                             ("superseded by later MKK disclosure", datetime_now_iso(), did))
                conn.commit()
                continue
            # A monthly report is a complete snapshot, not a delta. Delete old
            # positions first so a correction that removes an ISIN is visible.
            conn.execute("DELETE FROM fund_holdings WHERE code=? AND period=?",
                         (fund_code, period))
            conn.executemany(
                "INSERT INTO fund_holdings(code, period, isin, ticker, name, quantity, "
                "value, weight_pct, disclosure_id, source, attachment_id, "
                "attachment_sha256, parser_version, published_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(fund_code, period, h["isin"], h["ticker"], h["name"],
                  h["quantity"], h["value"], h["weight_pct"], did, "mkk-api",
                  selected_id, digest, MKK_PARSER_VERSION, published_at)
                 for h in holdings],
            )
            conn.execute("UPDATE mkk_disclosures SET status='parsed', last_error=NULL, "
                         "checked_at=? WHERE disclosure_index=?",
                         (datetime_now_iso(), did))
            conn.commit()
            parsed += 1
            print(f"  MKK {did} {fund_code}: {len(holdings)} holdings ({period})")
        except Exception as exc:
            conn.execute("UPDATE mkk_disclosures SET status='error', last_error=?, "
                         "checked_at=? WHERE disclosure_index=?",
                         (str(exc)[:500], datetime_now_iso(), did))
            conn.commit()
            errors += 1
            print(f"  MKK {did} ERROR: {exc}")
    return {"parsed": parsed, "errors": errors}


def requeue_legacy_errors(conn: sqlite3.Connection, limit: int = 50) -> dict:
    """Give pre-retry-ledger errors one controlled recovery attempt.

    Older cached rows have no recorded reason, so they cannot be safely
    classified as transient or terminal. Requeue each only once; subsequent
    failures record a reason and remain terminal until an operator fixes a
    parser/template and explicitly runs ``holdings reparse``.
    """
    _ensure_schema(conn)
    ids = [row[0] for row in conn.execute(
        "SELECT id FROM kap_disclosures WHERE status='error' "
        "AND last_error IS NULL ORDER BY id DESC LIMIT ?", (limit,))]
    if ids:
        conn.executemany(
            "UPDATE kap_disclosures SET status='retry', attempts=0 "
            "WHERE id=?", ((did,) for did in ids))
        conn.commit()
    return {"requeued": len(ids)}


def requeue_errors(conn: sqlite3.Connection, limit: int = 50) -> dict:
    """Operator-triggered retry after a parser or mapping change."""
    _ensure_schema(conn)
    ids = [row[0] for row in conn.execute(
        "SELECT id FROM kap_disclosures WHERE status='error' "
        "ORDER BY id DESC LIMIT ?", (limit,))]
    if ids:
        conn.executemany(
            "UPDATE kap_disclosures SET status='retry', attempts=0, "
            "last_error=NULL WHERE id=?", ((did,) for did in ids))
        conn.commit()
    return {"requeued": len(ids)}


def error_report(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """Return terminal parser/mapping failures for template triage."""
    _ensure_schema(conn)
    rows = conn.execute(
        "SELECT id, fund_title, code, year, period, attempts, last_error "
        "FROM kap_disclosures WHERE status='error' ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    keys = ("id", "fund_title", "code", "year", "period", "attempts", "last_error")
    return [dict(zip(keys, row)) for row in rows]


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
