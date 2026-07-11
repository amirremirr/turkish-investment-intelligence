"""Chunked download of TEFAS history into SQLite.

TEFAS rejects queries longer than 1 month, so date ranges are split
into CHUNK_DAYS windows and fetched sequentially with a polite pause.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from . import client, db

CHUNK_DAYS = 28
PAUSE_SECONDS = 5.0  # TEFAS rate-limits aggressive polling (429)

# Non-weight keys in allocation rows; every other numeric field is an
# asset-class percentage column.
_ALLOC_META = {"fonKodu", "fonUnvan", "tarih", "bilFiyat", "rn"}


def _chunks(start: date, end: date):
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def ingest_range(start: date, end: date, fund_type: str = "YAT",
                 fund_code: str | None = None, with_allocations: bool = True,
                 db_path=db.DB_PATH) -> dict:
    """Download [start, end] and upsert into SQLite. Returns row counts."""
    conn = db.connect(db_path)
    session = client.make_session()
    totals = {"prices": 0, "allocations": 0, "chunks": 0}

    for chunk_start, chunk_end in _chunks(start, end):
        rows = client.fetch_history(session, chunk_start, chunk_end,
                                    fund_type, fund_code)
        fund_rows, price_rows = [], []
        for r in rows:
            code = r.get("fonKodu")
            if not code:
                continue
            price = r.get("fiyat")
            fund_rows.append((code, r.get("fonUnvan"), fund_type))
            price_rows.append((
                code, r["tarih"],
                float(price) if price else None,
                r.get("tedPaySayisi"),
                r.get("kisiSayisi"),
                r.get("portfoyBuyukluk"),
            ))
        db.upsert_funds(conn, list({f[0]: f for f in fund_rows}.values()))
        db.upsert_prices(conn, price_rows)
        totals["prices"] += len(price_rows)

        if with_allocations:
            alloc = client.fetch_allocation(session, chunk_start, chunk_end,
                                            fund_type, fund_code)
            alloc_rows = []
            for r in alloc:
                code = r.get("fonKodu")
                if not code:
                    continue
                iso = r["tarih"]
                for key, val in r.items():
                    if key in _ALLOC_META or not isinstance(val, (int, float)):
                        continue
                    if val:
                        alloc_rows.append((code, iso, key, float(val)))
            db.upsert_allocations(conn, alloc_rows)
            totals["allocations"] += len(alloc_rows)

        conn.commit()
        totals["chunks"] += 1
        print(f"  {chunk_start} .. {chunk_end}: "
              f"{len(price_rows)} price rows (total {totals['prices']})")
        time.sleep(PAUSE_SECONDS)

    conn.close()
    return totals


def update(fund_type: str = "YAT", with_allocations: bool = True,
           db_path=db.DB_PATH) -> dict:
    """Fetch everything since the last stored date (or last 30 days if empty)."""
    conn = db.connect(db_path)
    last = db.last_price_date(conn, fund_type)
    conn.close()
    start = (date.fromisoformat(last) + timedelta(days=1)) if last \
        else date.today() - timedelta(days=30)
    end = date.today()
    if start > end:
        print("Already up to date.")
        return {"prices": 0, "allocations": 0, "chunks": 0}
    print(f"Updating {fund_type} from {start} to {end}")
    return ingest_range(start, end, fund_type,
                        with_allocations=with_allocations, db_path=db_path)
