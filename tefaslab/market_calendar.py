"""BIST trading calendar + holiday-aware stock gap detection.

Turkish market holidays are painful to hardcode: fixed national days
plus the two religious bayram that move ~11 days earlier each year on
the lunar calendar, plus ad-hoc half-days. So the trading calendar is
DERIVED from the BIST100 index series instead — a day the index printed
a value is a day the market was open. That makes gap detection correct
by construction:

  - a stock missing on an index-trading day  -> a real ingest gap
  - a stock missing on a non-index day        -> the market was closed

Confusing the two is exactly how a freshness monitor ends up crying
wolf on every national holiday. Freshness is measured in *trading* days,
not calendar days, for the same reason.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

REF = "bist100"  # the index whose print days define "market open"


def trading_days(conn: sqlite3.Connection, ref: str = REF,
                 since: str | None = None) -> list[str]:
    """Sorted ISO dates on which the market was open (the index printed)."""
    q = "SELECT date FROM benchmarks WHERE series = ?"
    params: list = [ref]
    if since:
        q += " AND date >= ?"
        params.append(since)
    q += " ORDER BY date"
    return [r[0] for r in conn.execute(q, params).fetchall()]


def latest_trading_day(conn: sqlite3.Connection, ref: str = REF) -> str | None:
    row = conn.execute(
        "SELECT MAX(date) FROM benchmarks WHERE series = ?", (ref,)).fetchone()
    return row[0] if row else None


def trading_days_between(conn: sqlite3.Connection, after: str,
                         through: str, ref: str = REF) -> int:
    """Number of market-open days in (after, through] — i.e. how many
    trading sessions a series dated `after` is behind `through`."""
    return conn.execute(
        "SELECT COUNT(*) FROM benchmarks WHERE series = ? "
        "AND date > ? AND date <= ?", (ref, after, through)).fetchone()[0]


def stock_coverage(conn: sqlite3.Connection, lookback: int = 40,
                   ref: str = REF) -> pd.DataFrame:
    """Per market-open day over the last `lookback` trading days, the
    number of distinct tickers priced. The scale of the normal day is
    the yardstick a gap is measured against."""
    days = trading_days(conn, ref)[-lookback:]
    if not days:
        return pd.DataFrame(columns=["date", "n_stocks"])
    rows = conn.execute(
        "SELECT date, COUNT(DISTINCT ticker) FROM stock_prices "
        "WHERE date >= ? GROUP BY date", (days[0],)).fetchall()
    have = dict(rows)
    # index-open days with zero stock rows won't appear in the GROUP BY,
    # so seed every trading day at 0 first — those are the worst gaps.
    return pd.DataFrame({"date": days,
                         "n_stocks": [have.get(d, 0) for d in days]})


def gap_report(conn: sqlite3.Connection, lookback: int = 40,
               min_ratio: float = 0.5, ref: str = REF) -> dict:
    """Holiday-aware stock-ingest health:

    - stock_lag_sessions: how many market sessions the stock table is
      behind the index (0 = current; weekends/holidays don't count).
    - low_coverage_days: index-trading days whose ticker count fell below
      `min_ratio` of the median — the market was open but our ingest
      largely wasn't.
    """
    market_day = latest_trading_day(conn, ref)
    stock_day = conn.execute("SELECT MAX(date) FROM stock_prices").fetchone()[0]
    lag = (trading_days_between(conn, stock_day, market_day, ref)
           if market_day and stock_day else None)

    cov = stock_coverage(conn, lookback, ref)
    low: list[tuple[str, int]] = []
    median = 0
    if not cov.empty:
        median = int(cov["n_stocks"].median())
        floor = min_ratio * median
        low = [(d, int(n)) for d, n in zip(cov["date"], cov["n_stocks"])
               if n < floor]
    return {
        "latest_market_day": market_day,
        "latest_stock_day": stock_day,
        "stock_lag_sessions": lag,
        "median_coverage": median,
        "low_coverage_days": low,
    }
