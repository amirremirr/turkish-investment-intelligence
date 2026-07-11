"""Stock-market intelligence: movers, breadth, sector performance.

All computed from the stock_prices and benchmarks tables — no extra
network calls, so the dashboard stays fast.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm



def _price_frame(conn: sqlite3.Connection, days: int = 90) -> pd.DataFrame:
    cutoff = conn.execute(
        "SELECT date FROM (SELECT DISTINCT date FROM stock_prices "
        "ORDER BY date DESC LIMIT ?) ORDER BY date LIMIT 1",
        (days,)).fetchone()
    if not cutoff:
        return pd.DataFrame()
    df = pd.read_sql_query(
        "SELECT ticker, date, close, volume FROM stock_prices "
        "WHERE date >= ?", conn, params=(cutoff[0],), parse_dates=["date"])
    return df


def movers(conn: sqlite3.Connection, n: int = 10,
           min_volume_try: float = 10e6) -> dict[str, pd.DataFrame]:
    """Top gainers/losers (1d), highest turnover, unusual volume."""
    df = _price_frame(conn, days=30)
    if df.empty:
        return {}
    close = df.pivot_table(index="date", columns="ticker", values="close")
    volume = df.pivot_table(index="date", columns="ticker", values="volume")
    turnover = close * volume  # approx TRY turnover

    ret_1d = close.iloc[-1] / close.iloc[-2] - 1
    ret_1w = close.iloc[-1] / close.iloc[-6] - 1 if len(close) > 6 else np.nan
    vol_avg20 = volume.iloc[:-1].tail(20).mean()
    vol_ratio = volume.iloc[-1] / vol_avg20

    titles = pd.read_sql_query(
        "SELECT ticker, title FROM stocks", conn).set_index("ticker")["title"]

    liquid = turnover.iloc[-1] >= min_volume_try
    base = pd.DataFrame({
        "close": close.iloc[-1],
        "ret_1d": ret_1d,
        "ret_1w": ret_1w,
        "turnover_mn": turnover.iloc[-1] / 1e6,
        "vol_vs_20d": vol_ratio,
    })[liquid].join(titles)

    return {
        "gainers": base.nlargest(n, "ret_1d"),
        "losers": base.nsmallest(n, "ret_1d"),
        "turnover": base.nlargest(n, "turnover_mn"),
        "unusual_volume": base[base["vol_vs_20d"] > 2]
        .nlargest(n, "vol_vs_20d"),
    }


def breadth(conn: sqlite3.Connection) -> dict:
    """Advance/decline, % above 50d MA, aggregate turnover."""
    df = _price_frame(conn, days=70)
    if df.empty:
        return {}
    close = df.pivot_table(index="date", columns="ticker", values="close")
    volume = df.pivot_table(index="date", columns="ticker", values="volume")
    ret_1d = close.iloc[-1] / close.iloc[-2] - 1
    advancers = int((ret_1d > 0.001).sum())
    decliners = int((ret_1d < -0.001).sum())
    ma50 = close.tail(50).mean()
    above_ma = float((close.iloc[-1] > ma50).mean()) * 100
    turnover = float((close.iloc[-1] * volume.iloc[-1]).sum() / 1e9)
    return {
        "date": str(close.index[-1].date()),
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": int(len(ret_1d.dropna()) - advancers - decliners),
        "adv_dec_ratio": round(advancers / max(decliners, 1), 2),
        "pct_above_50d_ma": round(above_ma, 1),
        "turnover_bn_try": round(turnover, 1),
    }


def sector_performance(conn: sqlite3.Connection,
                       min_stocks: int = 5) -> pd.DataFrame:
    """Equal-weight median sector returns computed from stock_prices,
    grouped by the Yahoo sector tag on the stocks table. 1d/1w/1m."""
    sectors = pd.read_sql_query(
        "SELECT ticker, sector FROM stocks "
        "WHERE sector IS NOT NULL AND sector != 'Unknown'",
        conn).set_index("ticker")["sector"]
    if sectors.empty:
        return pd.DataFrame()
    df = _price_frame(conn, days=30)
    if df.empty:
        return pd.DataFrame()
    close = df.pivot_table(index="date", columns="ticker", values="close")

    rows = []
    for sector, tickers in sectors.groupby(sectors).groups.items():
        cols = [t for t in tickers if t in close.columns]
        if len(cols) < min_stocks:
            continue
        c = close[cols]
        rows.append({
            "sector": sector,
            "stocks": len(cols),
            "ret_1d": (c.iloc[-1] / c.iloc[-2] - 1).median(),
            "ret_1w": (c.iloc[-1] / c.iloc[-6] - 1).median()
            if len(c) > 6 else np.nan,
            "ret_1m": (c.iloc[-1] / c.iloc[0] - 1).median(),
        })
    return pd.DataFrame(rows).set_index("sector") \
        .sort_values("ret_1d", ascending=False)


def market_snapshot(conn: sqlite3.Connection) -> dict:
    """Headline macro/market numbers for the executive view."""
    out = {}
    for series, label in [("bist100", "BIST100"), ("usdtry", "USD/TRY"),
                          ("gold_try_gram", "Gram gold (TRY)"),
                          ("nasdaq", "Nasdaq")]:
        s = bm.load_series(conn, series)
        if s.empty:
            continue
        out[label] = {"level": float(s.iloc[-1]),
                      "chg_1d": float(s.iloc[-1] / s.iloc[-2] - 1),
                      "date": str(s.index[-1].date())}
    return out
