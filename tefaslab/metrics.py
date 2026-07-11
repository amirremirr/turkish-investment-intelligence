"""Risk and performance analytics computed from the prices table.

All metrics work on a wide daily NAV matrix (rows=dates, cols=fund codes).
Annualization uses 252 trading days. The risk-free rate is an annual
simple rate (e.g. 0.40 for 40%) — pass the current TR deposit/policy
rate for meaningful Sharpe values in a high-inflation market.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm
from . import db

TRADING_DAYS = 252

WINDOWS = {
    "ret_1m": 21,
    "ret_3m": 63,
    "ret_6m": 126,
    "ret_1y": 252,
}


def load_prices(conn: sqlite3.Connection, fund_type: str | None = None) -> pd.DataFrame:
    query = "SELECT p.code, p.date, p.price FROM prices p"
    params: tuple = ()
    if fund_type:
        query += " JOIN funds f ON f.code = p.code WHERE f.fund_type = ?"
        params = (fund_type,)
    df = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])
    wide = df.pivot_table(index="date", columns="code", values="price")
    wide = wide.replace(0, np.nan).sort_index()
    return wide


def window_return(prices: pd.DataFrame, days: int) -> pd.Series:
    """Total return over the trailing `days` observations."""
    if len(prices) <= days:
        return pd.Series(np.nan, index=prices.columns)
    return prices.iloc[-1] / prices.iloc[-1 - days] - 1


def max_drawdown(prices: pd.DataFrame) -> pd.Series:
    cummax = prices.cummax()
    dd = prices / cummax - 1
    return dd.min()


def compute_metrics(conn: sqlite3.Connection, fund_type: str | None = None,
                    rf: float = 0.0, min_obs: int = 20) -> pd.DataFrame:
    """One row per fund: trailing returns, annualized vol, Sharpe,
    Sortino, max drawdown, plus latest AUM and investor count."""
    prices = load_prices(conn, fund_type)
    returns = prices.pct_change(fill_method=None)

    valid = returns.count() >= min_obs
    returns = returns.loc[:, valid]
    prices = prices.loc[:, valid]

    rf_daily = rf / TRADING_DAYS
    excess = returns - rf_daily
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = excess.mean() / returns.std() * np.sqrt(TRADING_DAYS)

    downside = returns.where(returns < 0)
    downside_std = downside.std()
    sortino = excess.mean() / downside_std * np.sqrt(TRADING_DAYS)

    out = pd.DataFrame({
        "ann_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_dd": max_drawdown(prices),
        "n_obs": returns.count(),
    })
    for name, days in WINDOWS.items():
        out[name] = window_return(prices, days)

    # benchmark-relative: beta and 1y excess return vs BIST100 (if fetched)
    # NAV dated t reflects the t-1 close -> lag the benchmark 1 day
    bench = bm.load_series(conn, "bist100")
    out["beta"] = np.nan
    out["excess_1y"] = np.nan
    if not bench.empty:
        bench_ret = bench.pct_change().shift(1).reindex(returns.index)
        if bench_ret.count() >= min_obs:
            # pairwise-complete beta, fully vectorized (a per-column
            # .cov() loop takes seconds over ~2k funds)
            R = returns.to_numpy(dtype=float)
            b = bench_ret.to_numpy(dtype=float)
            mask = ~np.isnan(R) & ~np.isnan(b)[:, None]
            n = mask.sum(axis=0).astype(float)
            n[n < min_obs] = np.nan
            Rm = np.where(mask, R, 0.0)
            Bm = np.where(mask, b[:, None], 0.0)
            mean_r = Rm.sum(axis=0) / n
            mean_b = Bm.sum(axis=0) / n
            cov = (Rm * Bm).sum(axis=0) / n - mean_r * mean_b
            var_b = (Bm ** 2).sum(axis=0) / n - mean_b ** 2
            out["beta"] = pd.Series(cov / var_b, index=returns.columns)
            bench_wide = bench.reindex(prices.index).ffill().to_frame("b")
            bench_1y = window_return(bench_wide, WINDOWS["ret_1y"])["b"]
            out["excess_1y"] = out["ret_1y"] - bench_1y

    meta = pd.read_sql_query(
        """
        SELECT p.code, f.title, f.category, p.aum, p.investors
        FROM prices p
        JOIN funds f ON f.code = p.code
        JOIN (SELECT code, MAX(date) AS d FROM prices GROUP BY code) last
          ON last.code = p.code AND last.d = p.date
        """,
        conn,
    ).set_index("code")
    out = out.join(meta, how="left")
    cols = ["title", "category", "ret_1m", "ret_3m", "ret_6m", "ret_1y",
            "excess_1y", "beta", "ann_vol", "sharpe", "sortino", "max_dd",
            "aum", "investors", "n_obs"]
    return out[cols].sort_values("sharpe", ascending=False)


def fund_report(conn: sqlite3.Connection, code: str, rf: float = 0.0) -> dict:
    """Detailed report for one fund: metrics plus latest allocation."""
    code = code.upper()
    prices = pd.read_sql_query(
        "SELECT date, price, aum, investors FROM prices "
        "WHERE code = ? ORDER BY date", conn, params=(code,),
        parse_dates=["date"]).set_index("date")
    if prices.empty:
        raise KeyError(f"No data for fund {code}")
    title = conn.execute(
        "SELECT title FROM funds WHERE code = ?", (code,)).fetchone()
    nav = prices["price"].replace(0, np.nan)
    rets = nav.pct_change(fill_method=None).dropna()
    rf_daily = rf / TRADING_DAYS
    downside = rets.where(rets < 0).std()

    alloc = pd.read_sql_query(
        "SELECT asset, pct FROM allocations WHERE code = ? AND "
        "date = (SELECT MAX(date) FROM allocations WHERE code = ?) "
        "ORDER BY pct DESC", conn, params=(code, code))

    return {
        "code": code,
        "title": title[0] if title else None,
        "first_date": str(prices.index[0].date()),
        "last_date": str(prices.index[-1].date()),
        "last_nav": float(nav.iloc[-1]),
        "total_return": float(nav.iloc[-1] / nav.dropna().iloc[0] - 1),
        "ann_vol": float(rets.std() * np.sqrt(TRADING_DAYS)),
        "sharpe": float((rets.mean() - rf_daily) / rets.std() * np.sqrt(TRADING_DAYS))
        if rets.std() else np.nan,
        "sortino": float((rets.mean() - rf_daily) / downside * np.sqrt(TRADING_DAYS))
        if downside else np.nan,
        "max_dd": float((nav / nav.cummax() - 1).min()),
        "aum": float(prices["aum"].iloc[-1]) if pd.notna(prices["aum"].iloc[-1]) else None,
        "investors": int(prices["investors"].iloc[-1])
        if pd.notna(prices["investors"].iloc[-1]) else None,
        "allocation": alloc.to_dict("records"),
    }
