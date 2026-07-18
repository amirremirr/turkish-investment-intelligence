"""Research studies on the fund database.

1. flow_predictability — do category fund flows predict future BIST
   returns? (information vs. noise)
2. performance_chasing — do investors buy after returns happen?
   (behavioral finance)
3. closet_index — are "active" equity funds actually active?
   (beta/R^2/alpha triage)

Standard errors are Newey-West (HAC): overlapping multi-day horizons
induce serial correlation in residuals, so the lag length defaults to
the overlap length. Both naive and NW t-stats are reported.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm
from . import factors, flows, metrics


def _ols(y: np.ndarray, x: np.ndarray, nw_lags: int = 0) -> dict:
    """Univariate OLS with intercept. Returns beta, naive t, Newey-West
    t (Bartlett kernel, `nw_lags` lags), r2, n."""
    mask = np.isfinite(y) & np.isfinite(x)
    y, x = y[mask], x[mask]
    n = len(y)
    if n < 30:
        return {"beta": np.nan, "t_stat": np.nan, "nw_t": np.nan,
                "r2": np.nan, "n": n}
    X = np.column_stack([np.ones(n), x])
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = n - 2
    s2 = resid @ resid / dof
    xvar = ((x - x.mean()) ** 2).sum()
    se = np.sqrt(s2 / xvar)
    r2 = 1 - resid.var() / y.var() if y.var() > 0 else np.nan

    # Newey-West on the slope: sandwich (X'X)^-1 S (X'X)^-1
    xtx_inv = np.linalg.inv(X.T @ X)
    u = X * resid[:, None]                      # n x 2 score
    S = u.T @ u
    L = max(int(nw_lags), 0)
    for lag in range(1, L + 1):
        w = 1 - lag / (L + 1)                   # Bartlett weight
        gamma = u[lag:].T @ u[:-lag]
        S += w * (gamma + gamma.T)
    cov = xtx_inv @ S @ xtx_inv
    nw_se = np.sqrt(cov[1, 1])
    return {"beta": float(coef[1]), "t_stat": float(coef[1] / se),
            "nw_t": float(coef[1] / nw_se) if nw_se > 0 else np.nan,
            "r2": float(r2), "n": n}


def _category_flow_series(conn: sqlite3.Connection,
                          category: str) -> pd.Series:
    """Daily category net flow normalized by category AUM (in %)."""
    df = flows.load_flow_frame(conn)
    cats = pd.read_sql_query(
        "SELECT code, category FROM funds", conn).set_index("code")["category"]
    df = df[df["code"].map(cats) == category]
    daily_flow = df.groupby("date")["flow"].sum()
    aum = pd.read_sql_query(
        """
        SELECT p.date, SUM(p.aum) aum FROM prices p
        JOIN funds f ON f.code = p.code
        WHERE f.category = ? AND p.aum IS NOT NULL GROUP BY p.date
        """, conn, params=(category,), parse_dates=["date"]) \
        .set_index("date")["aum"]
    return (daily_flow / aum * 100).dropna()


def flow_predictability(conn: sqlite3.Connection,
                        category: str = "Equity Turkey",
                        horizons: tuple = (1, 5, 10, 21),
                        regime: str | None = None) -> pd.DataFrame:
    """Regress future BIST100 returns on today's category flow.

    regime: None (full sample), "high_vol" or "low_vol" — split by
    whether BIST100's trailing 21d volatility is above/below its median
    (Test A: is the contrarian effect a euphoria phenomenon?).
    """
    flow = _category_flow_series(conn, category)
    bist = bm.load_series(conn, "bist100")
    if regime:
        vol = bist.pct_change().rolling(21).std().reindex(flow.index)
        median = vol.median()
        mask = vol > median if regime == "high_vol" else vol <= median
        flow = flow[mask.fillna(False)]
    out = []
    for h in horizons:
        fwd = (bist.shift(-h) / bist - 1).reindex(flow.index)
        res = _ols(fwd.to_numpy() * 100, flow.to_numpy(), nw_lags=h)
        out.append({"horizon_days": h, **res})
    return pd.DataFrame(out).set_index("horizon_days")


def flow_predictability_oos(conn: sqlite3.Connection,
                            category: str = "Equity Turkey",
                            horizon: int = 21,
                            split: str = "2026-01-01") -> pd.DataFrame:
    """Out-of-sample check: estimate on the training window, verify the
    sign and magnitude hold in the holdout."""
    flow = _category_flow_series(conn, category)
    bist = bm.load_series(conn, "bist100")
    fwd = ((bist.shift(-horizon) / bist - 1) * 100).reindex(flow.index)
    cut = pd.Timestamp(split)
    rows = []
    for label, mask in [("train (pre-split)", flow.index < cut),
                        ("test (post-split)", flow.index >= cut),
                        ("full sample", flow.index.notna())]:
        res = _ols(fwd[mask].to_numpy(), flow[mask].to_numpy(),
                   nw_lags=horizon)
        rows.append({"sample": label, **res})
    return pd.DataFrame(rows).set_index("sample")


def flow_predictability_by_category(
        conn: sqlite3.Connection, horizon: int = 21,
        categories: tuple = ("Equity Turkey", "Foreign Equity",
                             "Precious Metals", "Money Market",
                             "Hedge (Serbest)")) -> pd.DataFrame:
    """Test B: the flow->return relationship per category, one horizon."""
    out = []
    for cat in categories:
        try:
            res = flow_predictability(conn, cat, horizons=(horizon,))
            out.append({"category": cat, **res.iloc[0].to_dict()})
        except Exception:
            continue
    return pd.DataFrame(out).set_index("category")


def performance_chasing(conn: sqlite3.Connection,
                        category: str = "Equity Turkey",
                        lookbacks: tuple = (5, 21, 63)) -> pd.DataFrame:
    """Regress this week's category flow on trailing category returns."""
    flow = _category_flow_series(conn, category)
    # equal-weight category return from fund NAVs
    prices = metrics.load_prices(conn)
    cats = pd.read_sql_query(
        "SELECT code, category FROM funds", conn).set_index("code")["category"]
    codes = [c for c in prices.columns if cats.get(c) == category]
    cat_ret = prices[codes].pct_change(fill_method=None).mean(axis=1)

    weekly_flow = flow.resample("W").sum()
    out = []
    for lb in lookbacks:
        trailing = ((1 + cat_ret).rolling(lb).apply(np.prod, raw=True) - 1) \
            .resample("W").last().shift(1)  # last week's trailing return
        aligned = pd.concat([weekly_flow.rename("flow"),
                             (trailing * 100).rename("ret")], axis=1).dropna()
        res = _ols(aligned["flow"].to_numpy(), aligned["ret"].to_numpy(),
                   nw_lags=max(lb // 5, 1))  # weekly data: lags in weeks
        out.append({"lookback_days": lb, **res})
    return pd.DataFrame(out).set_index("lookback_days")


def closet_index(conn: sqlite3.Connection, min_aum: float = 100e6,
                 min_obs: int = 126) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Classify Equity Turkey funds by how active they really are.

    Uses the rigor-corrected factor model (cash factor + restructuring
    jump clipping) so the alpha column is a true excess, not the naive
    over-zero figure, and NAV resets don't distort beta/R^2."""
    from . import rigor
    betas = factors.all_factor_betas(
        conn, min_obs=min_obs, rf_daily=rigor._cash_daily(conn),
        clip_returns=rigor.MAX_DAILY_MOVE)
    aum = pd.read_sql_query(
        """
        SELECT p.code, p.aum FROM prices p
        JOIN (SELECT code, MAX(date) d FROM prices GROUP BY code) l
          ON l.code = p.code AND l.d = p.date
        """, conn).set_index("code")["aum"]
    eq = betas[(betas["category"] == "Equity Turkey")
               & (aum.reindex(betas.index) >= min_aum)].copy()

    def bucket(row):
        if row["r_squared"] >= 0.85 and 0.85 <= row["beta_bist100"] <= 1.15:
            return "closet index"
        if row["r_squared"] < 0.60:
            return "true active"
        return "moderately active"

    eq["bucket"] = eq.apply(bucket, axis=1)
    summary = eq.groupby("bucket").agg(
        funds=("bucket", "size"),
        avg_beta=("beta_bist100", "mean"),
        avg_r2=("r_squared", "mean"),
        avg_alpha=("alpha_annual", "mean"),
    ).round(3)
    detail = eq[["title", "bucket", "beta_bist100", "r_squared",
                 "alpha_annual"]].sort_values("r_squared", ascending=False)
    return summary, detail
