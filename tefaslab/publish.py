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
from sqlalchemy import bindparam, create_engine, inspect, text

from . import db

# system_status is NOT here — it gets a key-level upsert (see
# _publish_status) so cloud-only rows survive a full-table replace.
FULL_TABLES = ["funds", "stocks", "benchmarks", "fund_holdings",
               "kap_disclosures"]
INCREMENTAL = {"prices": "date", "stock_prices": "date"}
SKIP = {"allocations", "live_quotes"}

# Read chunk: sidesteps a spurious numpy allocation bug on Windows when
# pandas dtype-infers a single huge (1M+ row) object array.
READ_CHUNK = 20_000
# Write chunk: `to_sql(method="multi")` compiles chunksize x n_columns
# parameters into ONE statement. Postgres caps bound parameters per
# statement at 65535; 2,000 rows stays well under that even for our
# widest table (dash_metrics, ~16 columns -> 32,000 params).
WRITE_CHUNK = 2_000

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


# Keys written directly to the serving DB by cloud jobs — the local
# publish must never touch them (the local copy of these is stale).
CLOUD_ONLY_STATUS = {"intraday"}


def _publish_status(src: sqlite3.Connection, engine) -> int:
    """Upsert system_status by key, refreshing only the keys the local
    pipeline owns. Cloud-only keys (e.g. 'intraday', written straight to
    Supabase by the intraday cron) are left completely untouched — a
    full-table replace would delete them, and re-publishing the local
    copy would overwrite fresh cloud data with a stale local row."""
    try:
        local = pd.read_sql_query("SELECT * FROM system_status", src)
    except Exception:
        return 0
    local = local[~local["key"].isin(CLOUD_ONLY_STATUS)]
    if not insp_has(engine, "system_status"):
        local.head(0).to_sql("system_status", engine, index=False)
    keys = local["key"].tolist()
    if keys:
        stmt = text("DELETE FROM system_status WHERE key IN :ks") \
            .bindparams(bindparam("ks", expanding=True))
        with engine.begin() as c:
            c.execute(stmt, {"ks": keys})
    if len(local):
        local.to_sql("system_status", engine, if_exists="append",
                     index=False)
    return len(local)


def insp_has(engine, table: str) -> bool:
    return inspect(engine).has_table(table)


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
                  chunksize=WRITE_CHUNK, method="multi")
        stats[name] = len(df)
        print(f"  {name:<22} {len(df):>9,} rows (replace)")

    # system_status: key-level upsert (preserves cloud-only 'intraday')
    n = _publish_status(src, engine)
    if n:
        stats["system_status"] = n
        print(f"  {'system_status':<22} {n:>9,} rows (upsert by key)")

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
        # Read in chunks: pandas' dtype inference over a single huge
        # object array (1M+ rows) hits a spurious numpy allocation bug
        # on Windows (tries to coerce to complex128, "fails" to
        # allocate a few MB). Smaller per-chunk arrays sidestep it, and
        # it caps memory during the network write regardless.
        total = 0
        for chunk in pd.read_sql_query(q, src, params=params,
                                       chunksize=READ_CHUNK):
            chunk.to_sql(name, engine, if_exists="append", index=False,
                        chunksize=WRITE_CHUNK, method="multi")
            total += len(chunk)
        stats[name] = total
        print(f"  {name:<22} {total:>9,} rows (append since {last})")

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
