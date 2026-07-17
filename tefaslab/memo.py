"""Automatic investment memos: turn analytics into a decision document.

Rule-based (deliberately not an LLM): every sentence traces to a number
in the database, so the memo is auditable. Output is markdown.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd

from . import factors, flows, metrics

FACTOR_LABELS = {
    "bist100": "Turkish equity (BIST100)",
    "gold_try": "gold",
    "usdtry": "USD/TRY",
    "nasdaq_try": "Nasdaq",
}


def generate_memo(conn: sqlite3.Connection, code: str, rf: float = 0.0,
                  table: pd.DataFrame | None = None) -> str:
    """`table`: optionally pass a precomputed metrics frame (e.g. the
    dash_metrics presentation table) to avoid recomputing all funds."""
    code = code.upper()
    if table is None:
        table = metrics.compute_metrics(conn, rf=rf)
    if code not in table.index:
        raise KeyError(f"No data for fund {code}")
    m = table.loc[code]
    peers = table[table["category"] == m["category"]]

    try:
        f = factors.fund_factor_model(conn, code)
    except (KeyError, ValueError):
        f = None

    flow = flows.load_flow_frame(conn)
    cutoff = flow["date"].max() - pd.Timedelta(days=90)
    flow90 = flow[(flow["date"] > cutoff) & (flow["code"] == code)]["flow"].sum()

    strengths, risks = [], []

    if pd.notna(m["excess_1y"]) and m["excess_1y"] > 0.05:
        strengths.append(f"Beat BIST100 by {m['excess_1y'] * 100:+.1f}pp "
                         "over the last year")
    elif pd.notna(m["excess_1y"]) and m["excess_1y"] < -0.05:
        risks.append(f"Underperformed BIST100 by "
                     f"{abs(m['excess_1y']) * 100:.1f}pp over the last year")

    if pd.notna(m["sharpe"]) and m["sharpe"] > peers["sharpe"].median():
        strengths.append(f"Sharpe {m['sharpe']:.2f} is above the "
                         f"{m['category']} median "
                         f"({peers['sharpe'].median():.2f})")
    # Same philosophy as the skill score: a noisy alpha on a short
    # sample is not a strength — require statistical significance
    # (|t| > 2), not just a big point estimate.
    if (f and f["alpha_annual"] > 0.10 and f["r_squared"] > 0.3
            and (f.get("alpha_t") or 0) > 2):
        strengths.append(f"Positive factor-adjusted performance "
                         f"(alpha ≈ {f['alpha_annual'] * 100:.0f}%/yr, "
                         f"t = {f['alpha_t']:.1f}, "
                         f"R² {f['r_squared']:.2f})")
    elif (f and f["alpha_annual"] > 0.10 and f["r_squared"] > 0.3):
        risks.append(f"Apparent alpha ({f['alpha_annual'] * 100:.0f}%/yr) "
                     f"is not statistically significant "
                     f"(t = {f.get('alpha_t') or float('nan'):.1f}) — "
                     "could be noise on a short sample")

    if f:
        drivers = {k: v["beta"] for k, v in f["factors"].items()}
        main = max(drivers, key=lambda k: abs(drivers[k]))
        if abs(drivers[main]) > 0.5:
            strengths.append(f"Clear mandate: primary driver is "
                             f"{FACTOR_LABELS[main]} "
                             f"(beta {drivers[main]:.2f})")
            if main in ("nasdaq_try",):
                risks.append("High foreign-market dependency; vulnerable "
                             "to Nasdaq corrections and would lag if TRY "
                             "strengthens")
            if main == "usdtry" or drivers.get("usdtry", 0) > 0.5:
                risks.append("Significant USD/TRY exposure")
        if f["r_squared"] < 0.25:
            risks.append(f"Low factor R² ({f['r_squared']:.2f}): returns "
                         "are hard to explain — could be skill, could be "
                         "unmodeled risk")

    if pd.notna(m["max_dd"]) and m["max_dd"] < -0.20:
        risks.append(f"Deep historical drawdown "
                     f"({m['max_dd'] * 100:.0f}%): expect large swings")
    if pd.notna(m["aum"]) and m["aum"] < 500e6:
        risks.append(f"Small fund (₺{m['aum'] / 1e6:.0f}mn AUM): "
                     "liquidity and pricing artifacts possible")
    if pd.notna(m["investors"]) and m["investors"] < 1000:
        risks.append(f"Narrow investor base ({int(m['investors'])}): "
                     "flows of a few holders can move the fund")
    if flow90 < -0.05 * m["aum"]:
        risks.append(f"Investors are leaving: ₺{flow90 / 1e6:,.0f}mn net "
                     "outflow in 90 days")
    elif flow90 > 0.05 * m["aum"]:
        strengths.append(f"Attracting capital: ₺{flow90 / 1e6:,.0f}mn net "
                         "inflow in 90 days")

    vol = m["ann_vol"] if pd.notna(m["ann_vol"]) else 0
    if vol < 0.10:
        profile = ("capital preservation and cash management",
                   "investors seeking equity-like returns")
    elif vol < 0.25:
        profile = ("medium-risk investors with a 1-3 year horizon",
                   "investors who cannot tolerate double-digit drawdowns")
    else:
        profile = ("long-term growth investors who can hold through "
                   "large drawdowns",
                   "low-volatility or short-horizon investors")

    lines = [
        f"# Investment memo: {code}",
        f"*{m['title']}*",
        "",
        f"**Category:** {m['category']} · **AUM:** ₺{m['aum'] / 1e9:.2f}B · "
        f"**Investors:** {int(m['investors']):,} · "
        f"**Generated:** {date.today()}"
        if pd.notna(m["investors"]) and pd.notna(m["aum"])
        else f"**Category:** {m['category']} · **Generated:** {date.today()}",
        "",
        "## Snapshot",
        f"- 1y return: {m['ret_1y'] * 100:.1f}%"
        if pd.notna(m["ret_1y"]) else "- 1y return: insufficient history",
        f"- vs BIST100 (1y): {m['excess_1y'] * 100:+.1f}pp"
        if pd.notna(m["excess_1y"]) else "- vs BIST100: n/a",
        f"- Volatility: {vol * 100:.0f}% · Sharpe: {m['sharpe']:.2f} · "
        f"Max drawdown: {m['max_dd'] * 100:.1f}%",
        "",
        "## Strengths",
        *(f"- {s}" for s in (strengths or ["None identified by rules"])),
        "",
        "## Risks",
        *(f"- {r}" for r in (risks or ["None identified by rules"])),
        "",
        "## Investor profile",
        f"- **Suitable for:** {profile[0]}",
        f"- **Not suitable for:** {profile[1]}",
        "",
        "---",
        "*Rule-based memo generated from TEFAS data; every statement "
        "traces to a computed metric. Not investment advice.*",
    ]
    return "\n".join(lines)
