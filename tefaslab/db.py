"""SQLite schema and upsert helpers for the TEFAS fund database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "funds.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS funds (
    code        TEXT PRIMARY KEY,
    title       TEXT,
    fund_type   TEXT NOT NULL            -- YAT (mutual) or EMK (pension)
);

CREATE TABLE IF NOT EXISTS prices (
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,           -- ISO yyyy-mm-dd
    price       REAL,                    -- NAV per share (TRY)
    shares      REAL,                    -- shares outstanding
    investors   INTEGER,                 -- number of investors
    aum         REAL,                    -- portfolio size (TRY)
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS allocations (
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,
    asset       TEXT NOT NULL,           -- TEFAS asset-class column code
    pct         REAL NOT NULL,
    PRIMARY KEY (code, date, asset)
);

CREATE TABLE IF NOT EXISTS benchmarks (
    series      TEXT NOT NULL,           -- bist100, usdtry, gold_try_gram, ...
    date        TEXT NOT NULL,
    value       REAL NOT NULL,
    PRIMARY KEY (series, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE INDEX IF NOT EXISTS idx_alloc_date ON allocations(date);
"""


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(funds)")}
    if "category" not in cols:
        conn.execute("ALTER TABLE funds ADD COLUMN category TEXT")
    return conn


def upsert_funds(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows: (code, title, fund_type)"""
    conn.executemany(
        "INSERT INTO funds(code, title, fund_type) VALUES (?, ?, ?) "
        "ON CONFLICT(code) DO UPDATE SET title=excluded.title",
        rows,
    )


def upsert_prices(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows: (code, date, price, shares, investors, aum)"""
    conn.executemany(
        "INSERT OR REPLACE INTO prices(code, date, price, shares, investors, aum) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def upsert_allocations(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows: (code, date, asset, pct)"""
    conn.executemany(
        "INSERT OR REPLACE INTO allocations(code, date, asset, pct) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )


def upsert_benchmarks(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """rows: (series, date, value)"""
    conn.executemany(
        "INSERT OR REPLACE INTO benchmarks(series, date, value) "
        "VALUES (?, ?, ?)",
        rows,
    )


def last_price_date(conn: sqlite3.Connection, fund_type: str | None = None) -> str | None:
    if fund_type:
        row = conn.execute(
            "SELECT MAX(p.date) FROM prices p JOIN funds f ON f.code = p.code "
            "WHERE f.fund_type = ?", (fund_type,)
        ).fetchone()
    else:
        row = conn.execute("SELECT MAX(date) FROM prices").fetchone()
    return row[0] if row else None
