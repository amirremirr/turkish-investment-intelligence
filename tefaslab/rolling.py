"""Rolling analytics for a single fund (Priority 4C).

63-trading-day (quarterly) rolling windows over daily returns: return,
volatility, Sharpe, beta vs BIST100, and running drawdown. Sampled at
month-ends for readable output; full daily series available via CSV.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm
from . import metrics

WINDOW = 63


def fund_rolling(conn: sqlite3.Connection, code: str, rf: float = 0.0,
                 window: int = WINDOW) -> pd.DataFrame:
    code = code.upper()
    nav = pd.read_sql_query(
        "SELECT date, price FROM prices WHERE code = ? ORDER BY date",
        conn, params=(code,), parse_dates=["date"]).set_index("date")["price"]
    nav = nav.replace(0, np.nan).dropna()
    if nav.empty:
        raise KeyError(f"No data for fund {code}")

    ret = nav.pct_change()
    rf_daily = rf / metrics.TRADING_DAYS
    ann = np.sqrt(metrics.TRADING_DAYS)

    out = pd.DataFrame(index=nav.index)
    out["roll_return"] = nav.pct_change(window)
    out["roll_vol"] = ret.rolling(window).std() * ann
    out["roll_sharpe"] = (ret.rolling(window).mean() - rf_daily) \
        / ret.rolling(window).std() * ann
    out["drawdown"] = nav / nav.cummax() - 1

    # NAV dated t reflects the t-1 close -> lag the benchmark 1 day
    bench = bm.load_series(conn, "bist100")
    if not bench.empty:
        bench_ret = bench.pct_change().shift(1).reindex(nav.index)
        cov = ret.rolling(window).cov(bench_ret)
        var = bench_ret.rolling(window).var()
        out["roll_beta"] = cov / var

    return out.dropna(how="all")


def monthly_view(rolling_df: pd.DataFrame) -> pd.DataFrame:
    """Month-end snapshots of the rolling series."""
    return rolling_df.resample("ME").last().dropna(how="all")
