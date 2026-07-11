"""Nightly analytics pipeline (ETL).

Transforms raw tables into presentation tables (dash_*) so the
dashboard is a pure viewer — it never computes, it SELECTs.

    raw:          prices, allocations, stocks, stock_prices, benchmarks
    derived ->    dash_metrics, dash_betas, dash_quality, ...
    metadata:     system_status (one row per pipeline step)

Run via `python -m tefaslab daily` (optionally with --skip-raw).
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime

from . import (benchmarks, classify, db, evds, factors, flows, health,
               ingest, metrics, quality, regime, research, smartmoney,
               stockintel, stocks)

PRESENTATION_RF = 0.40  # annual risk-free rate baked into dash tables


def _status(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_status (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)
    """)
    conn.execute(
        "INSERT OR REPLACE INTO system_status VALUES (?, ?, ?)",
        (key, json.dumps(value, ensure_ascii=False, default=str),
         datetime.now().isoformat(timespec="seconds")))
    conn.commit()


def get_status(conn: sqlite3.Connection) -> dict:
    try:
        rows = conn.execute(
            "SELECT key, value, updated_at FROM system_status").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {k: {"value": json.loads(v), "updated_at": ts}
            for k, v, ts in rows}


def update_raw(conn: sqlite3.Connection) -> None:
    """Refresh all raw data sources (network calls)."""
    print("== raw data ==")
    ingest.update(fund_type="YAT")
    ingest.update(fund_type="EMK")
    benchmarks.fetch_benchmarks(start="2024-01-01")
    evds.fetch_macro()
    stocks.update_registry(conn)
    stocks.update_prices(conn)
    classify.classify_all(conn)
    _status(conn, "raw_updated", True)


def build_presentation(conn: sqlite3.Connection,
                       rf: float = PRESENTATION_RF) -> None:
    """Recompute every dash_* table. No network access."""
    print("== presentation tables ==")

    def step(name, fn):
        t0 = time.perf_counter()
        result = fn()
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"  {name:<22} {elapsed:>6.2f}s")
        _status(conn, name, {"seconds": elapsed})
        return result

    m = step("dash_metrics", lambda: metrics.compute_metrics(conn, rf=rf))
    m.reset_index().to_sql("dash_metrics", conn, if_exists="replace",
                           index=False)

    b = step("dash_betas", lambda: factors.all_factor_betas(conn))
    b.reset_index().to_sql("dash_betas", conn, if_exists="replace",
                           index=False)

    q = step("dash_quality", lambda: quality.combined_scores(conn, rf=rf))
    q.reset_index().to_sql("dash_quality", conn, if_exists="replace",
                           index=False)

    cf = step("dash_cat_flows", lambda: smartmoney.category_flows(conn, 30))
    cf.reset_index().to_sql("dash_cat_flows", conn, if_exists="replace",
                            index=False)

    rot = step("dash_rotation", lambda: smartmoney.category_rotation(conn, 12))
    rot.reset_index().to_sql("dash_rotation", conn, if_exists="replace",
                             index=False)

    _status(conn, "risk_appetite", smartmoney.risk_appetite(conn, 30))

    summary, detail = step("dash_closet",
                           lambda: research.closet_index(conn, min_aum=500e6))
    summary.reset_index().to_sql("dash_closet_summary", conn,
                                 if_exists="replace", index=False)
    detail.reset_index().to_sql("dash_closet_detail", conn,
                                if_exists="replace", index=False)

    sect = step("dash_sectors", lambda: stockintel.sector_performance(conn))
    if not sect.empty:
        sect.reset_index().to_sql("dash_sectors", conn, if_exists="replace",
                                  index=False)

    mv = step("dash_movers", lambda: stockintel.movers(conn))
    if mv:
        import pandas as pd
        combined = pd.concat(mv, names=["board", "ticker"]).reset_index()
        combined.to_sql("dash_movers", conn, if_exists="replace", index=False)

    _status(conn, "breadth", stockintel.breadth(conn))
    _status(conn, "market_snapshot", stockintel.market_snapshot(conn))
    try:
        _status(conn, "macro_regime",
                {**regime.indicators(conn), **regime.classify(
                    regime.indicators(conn))})
    except Exception as err:
        print(f"  regime skipped: {err}")

    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("funds", "prices", "allocations", "stock_prices",
                        "benchmarks")}
    _status(conn, "row_counts", counts)
    _status(conn, "presentation_rf", rf)
    _status(conn, "pipeline_complete", True)


def run(skip_raw: bool = False, rf: float = PRESENTATION_RF) -> int:
    conn = db.connect()
    t0 = time.perf_counter()
    if not skip_raw:
        update_raw(conn)
    build_presentation(conn, rf=rf)
    print(f"\npipeline done in {time.perf_counter() - t0:.0f}s")
    print("\n== health ==")
    code = health.report(conn)
    conn.close()
    return code
