"""Turkish investment regime engine (Phase 2).

Classifies the macro environment from EVDS + market series and answers
the portfolio-manager question: "which fund categories work in this
regime, historically?"

Regime dimensions (each with explicit, documented thresholds):
  inflation   yoy CPI: HIGH ≥ 40% · ELEVATED 20-40% · MODERATE < 20%
  real rate   policy − expected-ish inflation proxy (yoy CPI):
              RESTRICTIVE > +5pp · NEUTRAL ±5pp · LOOSE < −5pp
  FX          3m USDTRY change: STRESS > 8% · DRIFT 2-8% · STABLE < 2%
  equity      3m BIST100 return sign
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm


def indicators(conn: sqlite3.Connection) -> dict:
    cpi = bm.load_series(conn, "cpi_index")
    policy = bm.load_series(conn, "policy_rate")
    dep3m = bm.load_series(conn, "deposit_3m")
    usd = bm.load_series(conn, "usdtry")
    bist = bm.load_series(conn, "bist100")

    out: dict = {}
    if len(cpi) >= 13:
        out["inflation_yoy"] = round(float(
            cpi.iloc[-1] / cpi.iloc[-13] - 1) * 100, 1)
        out["inflation_asof"] = str(cpi.index[-1].date())
        prev = float(cpi.iloc[-2] / cpi.iloc[-14] - 1) * 100
        out["inflation_trend"] = "falling" \
            if out["inflation_yoy"] < prev else "rising"
    if not policy.empty:
        out["policy_rate"] = round(float(policy.iloc[-1]), 1)
    if not dep3m.empty:
        out["deposit_3m"] = round(float(dep3m.iloc[-1]), 1)
    if "policy_rate" in out and "inflation_yoy" in out:
        out["real_rate"] = round(out["policy_rate"]
                                 - out["inflation_yoy"], 1)
    if len(usd) > 66:
        out["usdtry_3m_pct"] = round(float(
            usd.iloc[-1] / usd.iloc[-66] - 1) * 100, 1)
    if len(bist) > 66:
        out["bist_3m_pct"] = round(float(
            bist.iloc[-1] / bist.iloc[-66] - 1) * 100, 1)
    return out


def classify(ind: dict) -> dict:
    labels = {}
    infl = ind.get("inflation_yoy")
    if infl is not None:
        labels["inflation"] = ("HIGH" if infl >= 40 else
                               "ELEVATED" if infl >= 20 else "MODERATE")
        labels["inflation"] += f" ({ind.get('inflation_trend', '?')})"
    rr = ind.get("real_rate")
    if rr is not None:
        labels["rates"] = ("RESTRICTIVE" if rr > 5 else
                           "LOOSE" if rr < -5 else "NEUTRAL")
    fx = ind.get("usdtry_3m_pct")
    if fx is not None:
        labels["fx"] = ("STRESS" if fx > 8 else
                        "DRIFT" if fx > 2 else "STABLE")
    eq = ind.get("bist_3m_pct")
    if eq is not None:
        labels["equity_trend"] = "UP" if eq > 0 else "DOWN"
    return labels


def _monthly_regimes(conn: sqlite3.Connection) -> pd.DataFrame:
    """Label each month in the sample by rate and FX regime."""
    policy = bm.load_series(conn, "policy_rate").resample("ME").last()
    cpi = bm.load_series(conn, "cpi_index")
    infl = (cpi / cpi.shift(12) - 1).mul(100) \
        .resample("ME").last().reindex(policy.index).ffill()
    usd = bm.load_series(conn, "usdtry").resample("ME").last()
    fx_3m = usd.pct_change(3).mul(100).reindex(policy.index)

    df = pd.DataFrame({"real_rate": policy - infl, "fx_3m": fx_3m}).dropna()
    df["rates"] = np.where(df["real_rate"] > 5, "RESTRICTIVE",
                           np.where(df["real_rate"] < -5, "LOOSE",
                                    "NEUTRAL"))
    df["fx"] = np.where(df["fx_3m"] > 8, "STRESS",
                        np.where(df["fx_3m"] > 2, "DRIFT", "STABLE"))
    return df


def historical_winners(conn: sqlite3.Connection,
                       by: str = "rates") -> pd.DataFrame:
    """Median monthly category fund return within each regime bucket
    (nominal TRY, %). `by`: 'rates' or 'fx'."""
    regimes = _monthly_regimes(conn)
    prices = pd.read_sql_query(
        """
        SELECT p.date, f.category, p.code, p.price FROM prices p
        JOIN funds f ON f.code = p.code WHERE p.price > 0
        """, conn, parse_dates=["date"])
    wide = prices.pivot_table(index="date", columns=["category", "code"],
                              values="price")
    monthly = wide.resample("ME").last()
    rets = monthly.pct_change(fill_method=None)
    cat_ret = rets.T.groupby(level="category").median().T  # median fund

    joined = cat_ret.join(regimes[by], how="inner")
    out = joined.groupby(by).mean().T.mul(100).round(2)
    out["n_months"] = np.nan
    counts = regimes[by].value_counts()
    return out, counts


def report(conn: sqlite3.Connection) -> str:
    ind = indicators(conn)
    labels = classify(ind)
    lines = ["== macro indicators =="]
    for k, v in ind.items():
        lines.append(f"  {k}: {v}")
    lines.append("\n== current regime ==")
    for k, v in labels.items():
        lines.append(f"  {k}: {v}")
    winners, counts = historical_winners(conn, by="rates")
    lines.append("\n== median monthly category return by rate regime "
                 "(%, nominal) ==")
    lines.append("(months per regime: "
                 + ", ".join(f"{k}={v}" for k, v in counts.items()) + ")")
    lines.append(winners.drop(columns=["n_months"]).to_string())
    current = labels.get("rates")
    if current and current in winners.columns:
        top = winners[current].drop(index=["n_months"], errors="ignore") \
            .nlargest(3)
        lines.append(f"\nhistorically strongest in {current} months: "
                     + ", ".join(f"{c} ({v:+.1f}%/mo)"
                                 for c, v in top.items()))
    return "\n".join(lines)
