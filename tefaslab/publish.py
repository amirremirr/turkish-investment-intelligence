"""Publish the serving dataset to Supabase Postgres.

Architecture decision (v2.0): SQLite stays the local COMPUTE engine —
the nightly pipeline's millions of upserts are local and fast — and
Supabase Postgres is the SERVING copy for anything user-facing
(future Next.js frontend, Supabase REST/auth, third parties). The
publisher runs after the pipeline and syncs a curated set:

  full replace (small, changes shape freely):
      funds, stocks, benchmarks, fund_holdings, kap_disclosures,
      system_status, every dash_* presentation table
  incremental append (large, append-only by date):
      prices, stock_prices
  not published (too big for the serving tier, analytics-only):
      allocations (6M+ rows) — aggregate views can be added on demand

Connection: SUPABASE_DB_URL in env or .env
(postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres).
Everything goes through SQLAlchemy, so any Postgres works, and the
whole publisher can be smoke-tested against a sqlite:/// target URL.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from . import db

FULL_TABLES = ["funds", "stocks", "benchmarks", "fund_holdings",
               "kap_disclosures", "system_status"]
INCREMENTAL = {"prices": "date", "stock_prices": "date"}
SKIP = {"allocations", "live_quotes"}

CHUNK = 20_000

DDL_AFTER_INIT = [
    "ALTER TABLE prices ADD PRIMARY KEY (code, date)",
    "ALTER TABLE stock_prices ADD PRIMARY KEY (ticker, date)",
    "ALTER TABLE funds ADD PRIMARY KEY (code)",
    "ALTER TABLE stocks ADD PRIMARY KEY (ticker)",
    "CREATE INDEX IF NOT EXISTS idx_pub_prices_date ON prices(date)",
    "CREATE INDEX IF NOT EXISTS idx_pub_hold_ticker "
    "ON fund_holdings(ticker)",
]


def serving_url() -> str | None:
    if os.environ.get("SUPABASE_DB_URL"):
        return os.environ["SUPABASE_DB_URL"]
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("SUPABASE_DB_URL="):
                return line.split("=", 1)[1].strip()
    return None


def _dash_tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'dash_%'")]


def publish(url: str | None = None, init: bool = False,
            db_path=db.DB_PATH) -> dict:
    url = url or serving_url()
    if not url:
        print("  SUPABASE_DB_URL not set — skipping publish")
        return {}
    engine = create_engine(url)
    src = db.connect(db_path)
    stats: dict = {}
    t0 = time.perf_counter()

    tables = FULL_TABLES + _dash_tables(src)
    for name in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {name}", src)
        except Exception:
            continue
        df.to_sql(name, engine, if_exists="replace", index=False,
                  chunksize=CHUNK, method="multi")
        stats[name] = len(df)
        print(f"  {name:<22} {len(df):>9,} rows (replace)")

    insp = inspect(engine)
    src_tables = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for name, datecol in INCREMENTAL.items():
        if name not in src_tables:
            continue
        last = None
        if insp.has_table(name):
            with engine.connect() as c:
                last = c.execute(
                    text(f"SELECT MAX({datecol}) FROM {name}")).scalar()
        q = f"SELECT * FROM {name}"
        params = ()
        if last:
            q += f" WHERE {datecol} > ?"
            params = (last,)
        df = pd.read_sql_query(q, src, params=params)
        if len(df):
            df.to_sql(name, engine, if_exists="append", index=False,
                      chunksize=CHUNK, method="multi")
        stats[name] = len(df)
        print(f"  {name:<22} {len(df):>9,} rows (append since {last})")

    if init:
        with engine.begin() as c:
            for ddl in DDL_AFTER_INIT:
                try:
                    c.execute(text(ddl))
                except Exception as err:
                    print(f"  ddl skipped ({str(err)[:60]})")
    src.close()
    engine.dispose()
    stats["seconds"] = round(time.perf_counter() - t0, 1)
    return stats
