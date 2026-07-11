"""Two-score fund evaluation.

A single ranking conflates two different questions, so there are two:

Manager Skill Score — "Is this manager good?"
  35%  risk-adjusted alpha     (factor-model alpha)
  25%  consistency             (share of positive rolling 63d windows)
  20%  downside management     (max drawdown)
  20%  factor independence     (1 - R^2: how much of the return is
                                decisions rather than factor exposure)

Investor Suitability Score — "Should a typical investor buy this?"
  30%  risk-adjusted performance (Sharpe)
  20%  drawdown protection
  20%  AUM stability            (low volatility of weekly flows/AUM)
  15%  liquidity                (investor base size)
  15%  fund size                (AUM)

A tiny hedge-like fund can top Skill while ranking poorly on
Suitability — that separation is the point. Percentiles are computed
within the filtered universe. Fee data is not in TEFAS's API; when an
expense-ratio source is added it belongs in Suitability.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import factors, flows, metrics

SKILL_WEIGHTS = {
    "alpha": 0.35,
    "consistency": 0.25,
    "downside": 0.20,
    "independence": 0.20,
}

SUITABILITY_WEIGHTS = {
    "performance": 0.30,
    "drawdown": 0.20,
    "aum_stability": 0.20,
    "liquidity": 0.15,
    "size": 0.15,
}

RETENTION_DAYS = 90


def _components(conn: sqlite3.Connection, rf: float, min_aum: float,
                min_investors: int, min_obs: int) -> pd.DataFrame:
    base = metrics.compute_metrics(conn, rf=rf, min_obs=min_obs)
    base = base[(base["aum"] >= min_aum)
                & (base["investors"] >= min_investors)]

    prices = metrics.load_prices(conn)[base.index.tolist()]
    roll = prices.pct_change(63, fill_method=None)
    base["consistency"] = ((roll > 0).sum() / roll.notna().sum()) \
        .reindex(base.index)

    betas = factors.all_factor_betas(conn, min_obs=60)
    base["alpha_annual"] = betas["alpha_annual"].reindex(base.index)
    base["r_squared"] = betas["r_squared"].reindex(base.index)

    flow = flows.load_flow_frame(conn)
    cutoff = flow["date"].max() - pd.Timedelta(days=RETENTION_DAYS)
    recent = flow[flow["date"] > cutoff]
    weekly = recent.set_index("date").groupby("code")["flow"] \
        .resample("W").sum().reset_index()
    flow_vol = weekly.groupby("code")["flow"].std()
    base["retention_90d"] = (recent.groupby("code")["flow"].sum()
                             .reindex(base.index) / base["aum"]).fillna(0)
    base["flow_volatility"] = (flow_vol.reindex(base.index)
                               / base["aum"]).fillna(0)
    return base


def skill_scores(conn: sqlite3.Connection, rf: float = 0.0,
                 min_aum: float = 100e6, min_investors: int = 500,
                 min_obs: int = 126,
                 components: pd.DataFrame | None = None) -> pd.DataFrame:
    c = components if components is not None \
        else _components(conn, rf, min_aum, min_investors, min_obs)
    pct = pd.DataFrame({
        "alpha": c["alpha_annual"].rank(pct=True),
        "consistency": c["consistency"].rank(pct=True),
        "downside": c["max_dd"].rank(pct=True),
        "independence": (1 - c["r_squared"]).rank(pct=True),
    })
    score = sum(pct[k].fillna(0.5) * w for k, w in SKILL_WEIGHTS.items()) * 100
    out = c[["title", "category", "ret_1y", "sharpe", "max_dd",
             "alpha_annual", "consistency", "r_squared", "aum"]].copy()
    out["skill_score"] = score.round(1)
    return out.sort_values("skill_score", ascending=False)


def suitability_scores(conn: sqlite3.Connection, rf: float = 0.0,
                       min_aum: float = 100e6, min_investors: int = 500,
                       min_obs: int = 126,
                       components: pd.DataFrame | None = None) -> pd.DataFrame:
    c = components if components is not None \
        else _components(conn, rf, min_aum, min_investors, min_obs)
    pct = pd.DataFrame({
        "performance": c["sharpe"].rank(pct=True),
        "drawdown": c["max_dd"].rank(pct=True),
        "aum_stability": (-c["flow_volatility"]).rank(pct=True),
        "liquidity": c["investors"].rank(pct=True),
        "size": c["aum"].rank(pct=True),
    })
    score = sum(pct[k].fillna(0.5) * w
                for k, w in SUITABILITY_WEIGHTS.items()) * 100
    out = c[["title", "category", "ret_1y", "sharpe", "max_dd",
             "retention_90d", "aum", "investors"]].copy()
    out["suitability_score"] = score.round(1)
    return out.sort_values("suitability_score", ascending=False)


def combined_scores(conn: sqlite3.Connection, rf: float = 0.0,
                    **kwargs) -> pd.DataFrame:
    c = _components(conn, rf, kwargs.get("min_aum", 100e6),
                    kwargs.get("min_investors", 500),
                    kwargs.get("min_obs", 126))
    skill = skill_scores(conn, rf=rf, components=c, **kwargs)
    suit = suitability_scores(conn, rf=rf, components=c, **kwargs)
    out = skill[["title", "category", "ret_1y", "sharpe", "max_dd",
                 "alpha_annual", "aum", "skill_score"]].join(
        suit["suitability_score"])
    return out.sort_values("skill_score", ascending=False)


# backward compatibility for callers of the old single score
def quality_scores(conn: sqlite3.Connection, rf: float = 0.0,
                   **kwargs) -> pd.DataFrame:
    out = combined_scores(conn, rf=rf, **kwargs)
    out["quality_score"] = ((out["skill_score"]
                             + out["suitability_score"]) / 2).round(1)
    return out.sort_values("quality_score", ascending=False)
