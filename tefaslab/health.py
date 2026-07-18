"""Data quality monitoring.

Checks the database for the failure modes financial pipelines actually
hit: stale data, coverage gaps, impossible values, suspicious returns.
Exit code 1 if any check fails hard (for schedulers/CI).
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd

from . import market_calendar

OK, WARN, FAIL = "OK", "WARN", "FAIL"


def run_checks(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Returns (status, check, detail) tuples."""
    results = []

    def add(status, check, detail=""):
        results.append((status, check, detail))

    last = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    if last is None:
        add(FAIL, "prices table", "empty")
        return results
    staleness = (date.today() - date.fromisoformat(last)).days
    add(OK if staleness <= 4 else WARN, "price freshness",
        f"latest {last} ({staleness}d old)")

    n_funds = conn.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
    n_latest = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE date = ?", (last,)).fetchone()[0]
    add(OK if n_latest > 0.7 * n_funds else WARN,
        "latest-day coverage", f"{n_latest}/{n_funds} funds priced on {last}")

    # funds that stopped reporting (had prices, none in last 10 days)
    stale_funds = conn.execute(
        """
        SELECT COUNT(*) FROM
          (SELECT code, MAX(date) d FROM prices GROUP BY code)
        WHERE d < date(?, '-10 days')
        """, (last,)).fetchone()[0]
    add(OK if stale_funds < 0.15 * n_funds else WARN,
        "stale funds", f"{stale_funds} funds with no price in 10+ days "
        "(closures/mergers are normal)")

    # stock gap detection, holiday-aware: freshness is in *market
    # sessions* (weekends/holidays don't count) and a coverage collapse
    # is only flagged on a day the index actually traded.
    if market_calendar.latest_trading_day(conn):
        gr = market_calendar.gap_report(conn)
        lag = gr["stock_lag_sessions"]
        low = gr["low_coverage_days"]
        if low:
            status = FAIL
            detail = (f"{len(low)} market-open day(s) with collapsed stock "
                      f"coverage (median {gr['median_coverage']}): "
                      f"{low[:3]}")
        elif lag is not None and lag > 1:
            status = WARN
            detail = (f"stocks {lag} market sessions behind the index "
                      f"(index {gr['latest_market_day']}, stocks "
                      f"{gr['latest_stock_day']})")
        else:
            status = OK
            detail = (f"stocks current with the index "
                      f"({gr['latest_stock_day']}, {lag or 0} sessions "
                      f"behind); median coverage {gr['median_coverage']}")
        add(status, "stock gap detection", detail)

    bad_vals = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE price <= 0 OR aum < 0").fetchone()[0]
    add(OK if bad_vals == 0 else FAIL,
        "impossible values", f"{bad_vals} rows with price<=0 or aum<0")

    # daily NAV moves beyond +/-50% — restructurings or bad data
    jumps = pd.read_sql_query(
        """
        SELECT code, date, price,
               LAG(price) OVER (PARTITION BY code ORDER BY date) prev
        FROM prices WHERE price > 0
        """, conn)
    jumps = jumps.dropna(subset=["prev"])
    ratio = jumps["price"] / jumps["prev"]
    outliers = jumps[(ratio > 1.5) | (ratio < 0.5)]
    add(OK if len(outliers) < 100 else WARN, "return outliers",
        f"{len(outliers)} daily moves beyond ±50% "
        f"({outliers['code'].nunique()} funds)")

    # allocation coverage on the latest allocation date
    alloc_last = conn.execute(
        "SELECT MAX(date) FROM allocations").fetchone()[0]
    if alloc_last:
        alloc_funds = conn.execute(
            "SELECT COUNT(DISTINCT code) FROM allocations WHERE date = ?",
            (alloc_last,)).fetchone()[0]
        add(OK if alloc_funds > 0.7 * n_latest else WARN,
            "allocation coverage",
            f"{alloc_funds} funds have allocations on {alloc_last}")
    else:
        add(WARN, "allocation coverage", "no allocation data")

    # date-range continuity: any calendar month with zero data
    months = pd.read_sql_query(
        "SELECT DISTINCT substr(date,1,7) m FROM prices ORDER BY m", conn)["m"]
    full = pd.period_range(months.iloc[0], months.iloc[-1], freq="M") \
        .strftime("%Y-%m")
    missing = sorted(set(full) - set(months))
    add(OK if not missing else FAIL, "month continuity",
        f"missing months: {missing}" if missing else
        f"{months.iloc[0]} .. {months.iloc[-1]} continuous")

    # benchmarks present and fresh (monthly/weekly macro series publish
    # with a lag and get their own, looser thresholds)
    slow = {"cpi_index": 75, "deposit_3m": 21, "deposit_1y": 21}
    b = conn.execute(
        "SELECT series, MAX(date) FROM benchmarks GROUP BY series").fetchall()
    if not b:
        add(WARN, "benchmarks", "none loaded — run `benchmarks` command")
    else:
        stale = [(s, d) for s, d in b
                 if (date.today() - date.fromisoformat(d)).days
                 > slow.get(s, 7)]
        add(OK if not stale else WARN, "benchmark freshness",
            f"{len(b)} series; stale: {stale or 'none'}")

    unclassified = conn.execute(
        "SELECT COUNT(*) FROM funds WHERE category IS NULL").fetchone()[0]
    add(OK if unclassified == 0 else WARN, "classification",
        f"{unclassified} funds without category")

    return results


def report(conn: sqlite3.Connection) -> int:
    """Print the health report; return exit code (0 ok, 1 any FAIL)."""
    results = run_checks(conn)
    icons = {OK: "✓", WARN: "⚠", FAIL: "✗"}
    width = max(len(c) for _, c, _ in results)
    for status, check, detail in results:
        print(f" {icons[status]} {check:<{width}}  {detail}")
    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n{len(results)} checks: "
          f"{len(results) - fails - warns} ok, {warns} warn, {fails} fail")
    return 1 if fails else 0
