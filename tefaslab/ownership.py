"""Holdings-based analytics: crowding, active share, attribution.

Built on fund_holdings (KAP monthly portfolio reports). Coverage grows
nightly with the id scanner — every metric here reports its own
universe size so thin coverage is visible, not hidden.

Active share caveat: official BIST index constituent weights are not
in the database, so active share is computed **vs the peer aggregate
portfolio** (value-weighted holdings of all covered funds in the same
category) — "how different is this fund from the crowd", which is the
crowding-adjacent question anyway. Index-based active share becomes
possible when constituent weights are added.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd


def _latest_period(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(period) FROM fund_holdings").fetchone()
    return row[0] if row else None


def crowding(conn: sqlite3.Connection, min_funds: int = 2) -> pd.DataFrame:
    """Per stock: how many covered funds hold it, with what conviction."""
    period = _latest_period(conn)
    df = pd.read_sql_query(
        """
        SELECT h.ticker, s.title, COUNT(*) n_funds,
               SUM(h.value) / 1e6 total_value_mn,
               AVG(h.weight_pct) avg_weight_pct,
               MAX(h.weight_pct) max_weight_pct,
               GROUP_CONCAT(h.code) held_by
        FROM fund_holdings h
        LEFT JOIN stocks s ON s.ticker = h.ticker
        WHERE h.period = ? AND h.ticker IS NOT NULL
        GROUP BY h.ticker HAVING n_funds >= ?
        ORDER BY n_funds DESC, total_value_mn DESC
        """, conn, params=(period, min_funds))
    n_universe = conn.execute(
        "SELECT COUNT(DISTINCT code) FROM fund_holdings WHERE period = ?",
        (period,)).fetchone()[0]
    df.attrs["period"] = period
    df.attrs["fund_universe"] = n_universe
    df["pct_of_covered_funds"] = (df["n_funds"] / n_universe * 100).round(0)
    return df


def _weights(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    """Fund x ISIN weight matrix for one period (TR + foreign)."""
    df = pd.read_sql_query(
        "SELECT code, isin, ticker, weight_pct FROM fund_holdings "
        "WHERE period = ? AND weight_pct IS NOT NULL", conn,
        params=(period,))
    return df


def peer_active_share(conn: sqlite3.Connection,
                      code: str | None = None) -> pd.DataFrame:
    """Active share vs the value-weighted peer-aggregate portfolio of
    the same category: AS = 0.5 * sum |w_fund - w_peers|, on renormalized
    security weights."""
    period = _latest_period(conn)
    w = _weights(conn, period)
    cats = pd.read_sql_query(
        "SELECT code, category, title FROM funds", conn).set_index("code")
    w["category"] = w["code"].map(cats["category"])

    out = []
    for cat, grp in w.groupby("category"):
        funds = grp["code"].unique()
        if len(funds) < 2:
            continue
        # renormalize each fund's disclosed security weights to 100
        piv = grp.pivot_table(index="isin", columns="code",
                              values="weight_pct", aggfunc="sum").fillna(0)
        piv = piv / piv.sum() * 100
        for f in funds:
            peers = piv.drop(columns=[f])
            peer_port = peers.mean(axis=1)
            peer_port = peer_port / peer_port.sum() * 100
            act = 0.5 * (piv[f] - peer_port).abs().sum()
            out.append({"code": f, "category": cat,
                        "peer_active_share": round(float(act), 1),
                        "n_peers": len(funds) - 1,
                        "n_holdings": int((piv[f] > 0).sum())})
    res = pd.DataFrame(out).set_index("code")
    res = res.join(cats["title"])
    res.attrs["period"] = period
    if code:
        res = res[res.index == code.upper()]
    return res.sort_values("peer_active_share", ascending=False)


def stock_attribution(conn: sqlite3.Connection, code: str) -> pd.DataFrame:
    """Contribution of each holding to the fund's return in the month
    AFTER the report date: weight x stock return (TR tickers with price
    data; foreign holdings lack local prices and land in the residual).
    """
    code = code.upper()
    period = conn.execute(
        "SELECT MAX(period) FROM fund_holdings WHERE code = ?",
        (code,)).fetchone()[0]
    if not period:
        raise KeyError(f"no holdings for {code}")
    hold = pd.read_sql_query(
        "SELECT ticker, name, weight_pct FROM fund_holdings "
        "WHERE code = ? AND period = ? AND weight_pct IS NOT NULL",
        conn, params=(code, period))

    year, month = map(int, period.split("-"))
    nm_year, nm_month = (year, month + 1) if month < 12 else (year + 1, 1)
    start = f"{year:04d}-{month:02d}-25"       # report is month-end
    end = f"{nm_year:04d}-{nm_month:02d}-32"

    px = pd.read_sql_query(
        "SELECT ticker, date, close FROM stock_prices "
        "WHERE date > ? AND date < ? AND ticker IN (%s)"
        % ",".join("?" * len(hold)), conn,
        params=[start, end] + hold["ticker"].tolist())
    rets = {}
    for t, g in px.groupby("ticker"):
        g = g.sort_values("date")
        # month-end to month-end: last price of report month -> last of next
        base = g[g["date"] < f"{nm_year:04d}-{nm_month:02d}-01"]
        after = g[g["date"] >= f"{nm_year:04d}-{nm_month:02d}-01"]
        if len(base) and len(after):
            rets[t] = after["close"].iloc[-1] / base["close"].iloc[-1] - 1

    hold["stock_ret_pct"] = hold["ticker"].map(
        {k: v * 100 for k, v in rets.items()})
    hold["contribution_pp"] = (hold["weight_pct"]
                               * hold["stock_ret_pct"] / 100)

    nav = pd.read_sql_query(
        "SELECT date, price FROM prices WHERE code = ? AND date > ? "
        "AND date < ? ORDER BY date", conn, params=(code, start, end))
    fund_ret = np.nan
    if len(nav) > 5:
        base = nav[nav["date"] < f"{nm_year:04d}-{nm_month:02d}-01"]
        after = nav[nav["date"] >= f"{nm_year:04d}-{nm_month:02d}-01"]
        if len(base) and len(after):
            fund_ret = (after["price"].iloc[-1]
                        / base["price"].iloc[-1] - 1) * 100

    hold = hold.sort_values("contribution_pp", ascending=False)
    hold.attrs["period"] = period
    hold.attrs["fund_return_pct"] = round(float(fund_ret), 2) \
        if np.isfinite(fund_ret) else None
    hold.attrs["explained_pp"] = round(
        float(hold["contribution_pp"].sum(skipna=True)), 2)
    return hold
