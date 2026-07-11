"""Monthly Intelligence Report — auto-generated markdown.

Assembles the presentation tables into a readable monthly document:
market summary, investor behaviour, category rotation, fund leaders,
closet-index watch, research highlights, data appendix. Rule-based and
auditable, like the memos: every number traces to a dash_* table.

Usage:  python -m tefaslab report [--save reports/]
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import pandas as pd


def _table(conn, name, index_col=None):
    try:
        df = pd.read_sql_query(f"SELECT * FROM {name}", conn)
    except Exception:
        return pd.DataFrame()
    if index_col and index_col in df.columns:
        df = df.set_index(index_col)
    return df


def _status(conn) -> dict:
    try:
        rows = conn.execute(
            "SELECT key, value FROM system_status").fetchall()
        return {k: json.loads(v) for k, v in rows}
    except sqlite3.OperationalError:
        return {}


def _md_table(df: pd.DataFrame, max_rows: int = 10) -> str:
    return df.head(max_rows).to_markdown()


def build_report(conn: sqlite3.Connection) -> str:
    s = _status(conn)
    snap = s.get("market_snapshot", {})
    breadth = s.get("breadth", {})
    mood = s.get("risk_appetite", {})
    counts = s.get("row_counts", {})

    metrics = _table(conn, "dash_metrics", "code")
    cf = _table(conn, "dash_cat_flows", "category")
    rot = _table(conn, "dash_rotation", "date")
    quality = _table(conn, "dash_quality", "code")
    closet = _table(conn, "dash_closet_summary", "bucket")
    sectors = _table(conn, "dash_sectors", "sector")

    today = date.today()
    lines = [
        f"# Turkish Investment Intelligence — {today:%B %Y}",
        f"*Auto-generated {today} from the BIST fund/stock database. "
        "Every figure traces to a stored table; not investment advice.*",
        "",
        "## 1. Market summary",
    ]

    if snap:
        for label, v in snap.items():
            lines.append(f"- **{label}**: {v['level']:,.1f} "
                         f"({v['chg_1d'] * 100:+.2f}% on {v['date']})")
    if breadth:
        lines += [
            f"- **Breadth** ({breadth.get('date')}): "
            f"{breadth.get('advancers')} advancers vs "
            f"{breadth.get('decliners')} decliners "
            f"(ratio {breadth.get('adv_dec_ratio')}); "
            f"{breadth.get('pct_above_50d_ma')}% of stocks above their "
            f"50-day average; equity turnover "
            f"₺{breadth.get('turnover_bn_try')}bn."]
    if not sectors.empty:
        best, worst = sectors.index[0], sectors.index[-1]
        lines.append(f"- **Sectors (1m, median stock)**: strongest "
                     f"{sectors['ret_1m'].idxmax()} "
                     f"({sectors['ret_1m'].max() * 100:+.1f}%), weakest "
                     f"{sectors['ret_1m'].idxmin()} "
                     f"({sectors['ret_1m'].min() * 100:+.1f}%).")

    lines += ["", "## 2. Investor behaviour"]
    if not metrics.empty:
        lines.append(f"- Total mutual fund AUM: "
                     f"**₺{metrics['aum'].sum() / 1e12:.2f} trillion** "
                     f"across {len(metrics):,} scored funds.")
    if not cf.empty:
        top_in = cf["net_flow_bn"].idxmax()
        top_out = cf["net_flow_bn"].idxmin()
        lines += [
            f"- 30-day net flow: **₺{cf['net_flow_try'].sum() / 1e9:+.0f}bn**.",
            f"- Largest inflow: **{top_in}** "
            f"(₺{cf.loc[top_in, 'net_flow_bn']:+.1f}bn). "
            f"Largest outflow: **{top_out}** "
            f"(₺{cf.loc[top_out, 'net_flow_bn']:+.1f}bn).",
        ]
    if mood:
        lines.append(f"- Risk appetite reading: **{mood.get('reading')}** "
                     f"(flow tilt to risk {mood.get('flow_tilt_to_risk')}; "
                     f"risk-asset AUM share "
                     f"{mood.get('risk_asset_aum_share_now')}% vs "
                     f"{mood.get('risk_asset_aum_share_year_ago')}% a "
                     "year ago).")

    if not rot.empty:
        lines += ["", "## 3. Category rotation (AUM share, %)", "",
                  _md_table(rot.tail(4).round(1))]

    if not quality.empty:
        lines += ["", "## 4. Fund leaders"]
        skill = quality.sort_values("skill_score", ascending=False).head(5)
        suit = quality.sort_values("suitability_score",
                                   ascending=False).head(5)
        lines += ["", "**Top Manager Skill**", ""]
        for code, r in skill.iterrows():
            lines.append(f"- `{code}` {str(r['title'])[:60]} — skill "
                         f"{r['skill_score']:.0f}, 1y "
                         f"{r['ret_1y'] * 100:.0f}%, maxDD "
                         f"{r['max_dd'] * 100:.0f}%")
        lines += ["", "**Top Investor Suitability**", ""]
        for code, r in suit.iterrows():
            lines.append(f"- `{code}` {str(r['title'])[:60]} — suitability "
                         f"{r['suitability_score']:.0f}, AUM "
                         f"₺{r['aum'] / 1e9:.1f}bn")

    if not closet.empty:
        lines += ["", "## 5. Closet index watch", "",
                  _md_table(closet.round(3)), "",
                  "*closet index = R² ≥ 0.85 with beta ≈ 1 vs BIST100: "
                  "index exposure sold at active fees.*"]

    lines += [
        "", "## 6. Research highlights",
        "- Equity-fund flows remain a mild **contrarian** signal, "
        "present only in low-volatility regimes and only for domestic "
        "equity (see Research Lab for current estimates).",
        "- Investors chase **63-day trailing returns**, not weekly "
        "moves — medium-term performance chasing.",
        "",
        "## Appendix — data coverage",
    ]
    if counts:
        for t, n in counts.items():
            lines.append(f"- {t}: {n:,} rows")
    lines += [f"- report generated: {today}", ""]
    return "\n".join(lines)
