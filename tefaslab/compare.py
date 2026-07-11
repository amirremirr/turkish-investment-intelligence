"""Fund comparison engine: side-by-side profile of 2-5 funds.

One column per fund, rows grouped as identity / performance / risk /
factor exposure / investors & flows / allocation.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import factors, flows, metrics


def compare_funds(conn: sqlite3.Connection, codes: list[str],
                  rf: float = 0.0, days: int = 252,
                  table: pd.DataFrame | None = None) -> pd.DataFrame:
    codes = [c.upper() for c in codes]
    if table is None:
        table = metrics.compute_metrics(conn, rf=rf)
    missing = [c for c in codes if c not in table.index]
    if missing:
        raise KeyError(f"No data for: {', '.join(missing)}")

    flow = flows.load_flow_frame(conn)
    cutoff = flow["date"].max() - pd.Timedelta(days=30)
    flow30 = flow[flow["date"] > cutoff].groupby("code")["flow"].sum()

    alloc = pd.read_sql_query(
        """
        SELECT a.code, a.asset, a.pct FROM allocations a
        JOIN (SELECT code, MAX(date) AS d FROM allocations GROUP BY code) m
          ON m.code = a.code AND m.d = a.date
        """, conn)

    rows: dict[str, dict] = {}
    for code in codes:
        m = table.loc[code]
        try:
            f = factors.fund_factor_model(conn, code, days=days)
        except (KeyError, ValueError):
            f = None
        top_alloc = alloc[alloc["code"] == code].nlargest(3, "pct")
        alloc_str = ", ".join(f"{r.asset} {r.pct:.0f}%"
                              for r in top_alloc.itertuples())
        rows[code] = {
            "title": (m["title"] or "")[:40],
            "category": m["category"],
            "-- performance --": "",
            "ret_1m %": round(m["ret_1m"] * 100, 1),
            "ret_3m %": round(m["ret_3m"] * 100, 1),
            "ret_1y %": round(m["ret_1y"] * 100, 1),
            "excess_1y vs BIST %": round(m["excess_1y"] * 100, 1),
            "-- risk --": "",
            "ann_vol": round(m["ann_vol"], 2),
            "sharpe": round(m["sharpe"], 2),
            "sortino": round(m["sortino"], 2),
            "max_drawdown %": round(m["max_dd"] * 100, 1),
            "-- factor exposure --": "",
            "beta_bist100": f["factors"]["bist100"]["beta"] if f else np.nan,
            "beta_gold": f["factors"]["gold_try"]["beta"] if f else np.nan,
            "beta_usdtry": f["factors"]["usdtry"]["beta"] if f else np.nan,
            "beta_nasdaq": f["factors"]["nasdaq_try"]["beta"] if f else np.nan,
            "r_squared": f["r_squared"] if f else np.nan,
            "unexplained_ret %": round(f["unexplained_return"] * 100, 1)
            if f else np.nan,
            "-- investors & flows --": "",
            "aum_bn_try": round(m["aum"] / 1e9, 2),
            "investors": int(m["investors"])
            if pd.notna(m["investors"]) else None,
            "flow_30d_mn_try": round(flow30.get(code, np.nan) / 1e6, 0),
            "-- allocation (top 3) --": "",
            "allocation": alloc_str,
        }
    return pd.DataFrame(rows)
