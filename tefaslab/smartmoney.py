"""Smart money view: where is Turkish investor capital moving?

Three lenses on the same question:
  1. category flows   — net new money per category (share-count based)
  2. category rotation — how the market's AUM mix shifts month by month
  3. risk appetite     — risky-asset share of AUM + flow direction
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from . import flows

RISK_ON = {"Equity Turkey", "Foreign Equity", "Hedge (Serbest)"}
RISK_OFF = {"Money Market", "Debt", "Precious Metals", "Participation"}


def category_flows(conn: sqlite3.Connection, days: int = 30) -> pd.DataFrame:
    """Net flow per category over the trailing window."""
    df = flows.load_flow_frame(conn)
    cutoff = df["date"].max() - pd.Timedelta(days=days)
    recent = df[df["date"] > cutoff]
    cats = pd.read_sql_query(
        "SELECT code, category FROM funds", conn).set_index("code")["category"]
    recent = recent.assign(category=recent["code"].map(cats))
    out = recent.groupby("category")["flow"].sum() \
        .sort_values(ascending=False).to_frame("net_flow_try")
    out["net_flow_bn"] = (out["net_flow_try"] / 1e9).round(2)
    return out


def category_rotation(conn: sqlite3.Connection,
                      months: int = 12) -> pd.DataFrame:
    """Month-end AUM share per category (%, rows sum to 100)."""
    aum = pd.read_sql_query(
        """
        SELECT p.date, f.category, SUM(p.aum) aum
        FROM prices p JOIN funds f ON f.code = p.code
        WHERE p.aum IS NOT NULL
        GROUP BY p.date, f.category
        """, conn, parse_dates=["date"])
    wide = aum.pivot_table(index="date", columns="category", values="aum")
    monthly = wide.resample("ME").last().dropna(how="all").tail(months)
    share = monthly.div(monthly.sum(axis=1), axis=0) * 100
    return share.round(1)


def risk_appetite(conn: sqlite3.Connection, days: int = 30) -> dict:
    """A simple fear/greed reading for the Turkish fund investor."""
    rotation = category_rotation(conn, months=13)
    latest = rotation.iloc[-1]
    year_ago = rotation.iloc[0]
    risk_share_now = sum(latest.get(c, 0) for c in RISK_ON)
    risk_share_then = sum(year_ago.get(c, 0) for c in RISK_ON)

    cf = category_flows(conn, days)["net_flow_try"]
    flow_on = sum(cf.get(c, 0) for c in RISK_ON)
    flow_off = sum(cf.get(c, 0) for c in RISK_OFF)
    total = abs(flow_on) + abs(flow_off)
    flow_tilt = flow_on / total if total else 0.0

    if flow_tilt > 0.6 and risk_share_now > risk_share_then:
        label = "RISK-ON (greed)"
    elif flow_tilt < 0.25:
        label = "RISK-OFF (fear)"
    else:
        label = "NEUTRAL"
    return {
        "risk_asset_aum_share_now": round(risk_share_now, 1),
        "risk_asset_aum_share_year_ago": round(risk_share_then, 1),
        f"flow_{days}d_risk_on_bn": round(flow_on / 1e9, 1),
        f"flow_{days}d_risk_off_bn": round(flow_off / 1e9, 1),
        "flow_tilt_to_risk": round(flow_tilt, 2),
        "reading": label,
    }
