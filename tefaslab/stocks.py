"""BIST individual stock data.

Ticker registry comes from KAP's listed-companies page (server-rendered,
so a plain GET works even though KAP's JSON API is bot-protected).
Prices come from Yahoo Finance (`<TICKER>.IS`), batched.

Caveat: Yahoo BIST data is solid for large caps but small tickers can
have gaps or odd split adjustments — treat single-stock anomalies with
suspicion before drawing conclusions.
"""

from __future__ import annotations

import re
import sqlite3

import pandas as pd
import requests
import yfinance as yf

from . import db

KAP_LIST_URL = "https://www.kap.org.tr/tr/bist-sirketler"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/126.0.0.0 Safari/537.36"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    ticker      TEXT PRIMARY KEY,
    title       TEXT,
    city        TEXT,
    sector      TEXT,
    industry    TEXT
);
CREATE TABLE IF NOT EXISTS stock_prices (
    ticker      TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        REAL, high REAL, low REAL, close REAL,
    volume      REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(date);
"""

BATCH = 80


def fetch_ticker_list() -> list[tuple[str, str, str]]:
    """(ticker, company title, city) for every listed company, from KAP.
    Multi-class listings ("ISATR, ISBTR, ISCTR") expand to one row each."""
    r = requests.get(KAP_LIST_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    pattern = (r'\\"kapMemberTitle\\":\\"(.*?)\\",'
               r'\\"relatedMemberTitle\\".*?'
               r'\\"stockCode\\":\\"([A-Z0-9, ]+)\\",'
               r'\\"cityName\\":\\"(.*?)\\"')
    rows = []
    for title, codes, city in re.findall(pattern, r.text):
        for code in codes.split(","):
            code = code.strip()
            if 3 <= len(code) <= 6:
                rows.append((code, title, city))
    if not rows:
        raise RuntimeError("KAP page format changed — no tickers parsed")
    return rows


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stocks)")}
    for col in ("sector", "industry"):
        if col not in cols:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {col} TEXT")


def enrich_sectors(conn: sqlite3.Connection,
                   only_missing: bool = True) -> int:
    """One-time-ish: fetch sector/industry per ticker from Yahoo.
    Slow (~1s/ticker) — run in the background."""
    _migrate(conn)
    q = "SELECT ticker FROM stocks"
    if only_missing:
        q += " WHERE sector IS NULL"
    # only tickers that actually trade (have prices)
    tickers = [t for (t,) in conn.execute(
        q + " AND ticker IN (SELECT DISTINCT ticker FROM stock_prices)"
        if only_missing else q)]
    done = 0
    for i, t in enumerate(tickers):
        try:
            info = yf.Ticker(f"{t}.IS").get_info()
            sector = info.get("sector")
            industry = info.get("industry")
        except Exception:
            sector, industry = None, None
        conn.execute("UPDATE stocks SET sector = ?, industry = ? "
                     "WHERE ticker = ?",
                     (sector or "Unknown", industry, t))
        done += 1
        if i % 25 == 0:
            conn.commit()
            print(f"  {i + 1}/{len(tickers)} ({t}: {sector})")
    conn.commit()
    return done


def update_registry(conn: sqlite3.Connection) -> int:
    _migrate(conn)
    rows = fetch_ticker_list()
    conn.executemany(
        "INSERT INTO stocks(ticker, title, city) VALUES (?, ?, ?) "
        "ON CONFLICT(ticker) DO UPDATE SET title=excluded.title",
        rows)
    conn.commit()
    return len(rows)


def ingest_prices(conn: sqlite3.Connection, start: str = "2024-01-01",
                  tickers: list[str] | None = None) -> int:
    """Download daily OHLCV for the registry (or a subset) into SQLite."""
    conn.executescript(SCHEMA)
    if tickers is None:
        tickers = [t for (t,) in
                   conn.execute("SELECT ticker FROM stocks ORDER BY ticker")]
    total = 0
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        data = yf.download([f"{t}.IS" for t in batch], start=start,
                           group_by="ticker", auto_adjust=True,
                           progress=False, threads=True)
        rows = []
        for t in batch:
            key = f"{t}.IS"
            try:
                df = data[key].dropna(how="all")
            except KeyError:
                continue
            for dt, r in df.iterrows():
                if pd.isna(r.get("Close")):
                    continue
                rows.append((t, dt.strftime("%Y-%m-%d"),
                             r.get("Open"), r.get("High"), r.get("Low"),
                             r.get("Close"), r.get("Volume")))
        conn.executemany(
            "INSERT OR REPLACE INTO stock_prices"
            "(ticker, date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
        total += len(rows)
        print(f"  batch {i // BATCH + 1}/"
              f"{(len(tickers) + BATCH - 1) // BATCH}: "
              f"+{len(rows)} rows (total {total:,})")
    return total


def update_prices(conn: sqlite3.Connection) -> int:
    """Incremental: fetch from the last stored date."""
    conn.executescript(SCHEMA)
    last = conn.execute("SELECT MAX(date) FROM stock_prices").fetchone()[0]
    start = last or "2024-01-01"
    return ingest_prices(conn, start=start)
