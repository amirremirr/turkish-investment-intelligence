"""Fund flow estimation (Priority 2).

TEFAS gives shares outstanding (tedPaySayisi) and NAV daily, so net
flow is computed directly rather than inferred from AUM:

    net_flow_t = (shares_t - shares_{t-1}) * price_t

which is equivalent to AUM_t - AUM_{t-1} * (1 + r_t) but immune to
valuation noise. Positive = money entering the fund.

Restructuring guard: rows where the daily NAV moves more than
MAX_NAV_MOVE are excluded — those are share consolidations / unit
restructurings, not investor flows (audit found a single such event
carrying a fictitious -1.3 trillion TRY "flow").
"""

from __future__ import annotations

import sqlite3

import pandas as pd

MAX_NAV_MOVE = 0.50  # |daily NAV return| beyond this = restructuring


def load_flow_frame(conn: sqlite3.Connection,
                    fund_type: str | None = None) -> pd.DataFrame:
    """Long frame: code, date, price, shares, flow (TRY)."""
    query = ("SELECT p.code, p.date, p.price, p.shares FROM prices p "
             "WHERE p.price IS NOT NULL AND p.shares IS NOT NULL")
    params: tuple = ()
    if fund_type:
        query = ("SELECT p.code, p.date, p.price, p.shares FROM prices p "
                 "JOIN funds f ON f.code = p.code "
                 "WHERE p.price IS NOT NULL AND p.shares IS NOT NULL "
                 "AND f.fund_type = ?")
        params = (fund_type,)
    df = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])
    df = df.sort_values(["code", "date"])
    nav_ret = df.groupby("code")["price"].pct_change(fill_method=None)
    df["flow"] = df.groupby("code")["shares"].diff() * df["price"]
    df.loc[nav_ret.abs() > MAX_NAV_MOVE, "flow"] = pd.NA
    return df.dropna(subset=["flow"])


def market_flows(conn: sqlite3.Connection, days: int = 30,
                 fund_type: str | None = None) -> pd.DataFrame:
    """Total daily net flow across all funds, last `days` days."""
    df = load_flow_frame(conn, fund_type)
    daily = df.groupby("date")["flow"].sum().tail(days)
    return daily.to_frame("net_flow_try")


def top_fund_flows(conn: sqlite3.Connection, days: int = 30, n: int = 15,
                   fund_type: str | None = None) -> pd.DataFrame:
    """Funds ranked by cumulative net flow over the trailing window."""
    df = load_flow_frame(conn, fund_type)
    cutoff = df["date"].max() - pd.Timedelta(days=days)
    recent = df[df["date"] > cutoff]
    per_fund = recent.groupby("code")["flow"].sum().sort_values()

    meta = pd.read_sql_query(
        "SELECT code, title, category FROM funds", conn).set_index("code")
    out = per_fund.to_frame("net_flow_try").join(meta)
    inflows = out.tail(n).iloc[::-1]
    outflows = out.head(n)
    return pd.concat([inflows, outflows],
                     keys=["inflows", "outflows"], names=["side"])
