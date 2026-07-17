"""Factor exposure and return attribution (Priorities 4A + 4B).

Per fund, OLS regression of overlapping K-day returns on benchmark
factor returns:

    r_fund = alpha + b1*r_BIST100 + b2*r_gold(TRY) + b3*r_USDTRY
             + b4*r_Nasdaq(TRY) + eps

Two empirically-verified timing corrections (see git history / README):

- TEFAS NAV dated t reflects the t-1 close, so **domestic factors are
  lagged 1 day** (a BIST30 index fund then shows beta 0.995 vs 0.12
  unlagged).
- Globally-priced factors (Nasdaq, gold, USD) add one more day of lag
  (US close happens after the Turkish close) -> **lag 2**.
- Residual misalignment is absorbed by regressing K-day (default 5)
  overlapping compound returns instead of daily returns.

Attribution over the window follows from the betas:

    contribution_i = beta_i * factor_total_return_i
    unexplained return = fund_total_return - sum(contributions)

The residual is deliberately labeled *unexplained return*, not alpha:
it bundles timing differences, missing factors (sector tilts, foreign
markets not in the model), holdings differences, and model error along
with any true manager skill. Separating true alpha (stock selection +
timing) requires holdings data — see the KAP roadmap item.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm
from . import metrics

# label -> (benchmark series, lag in trading days)
FACTORS = {
    "bist100": ("bist100", 1),
    "gold_try": ("gold_try_gram", 2),
    "usdtry": ("usdtry", 2),
    "nasdaq_try": ("nasdaq_try", 2),
}

K_DAYS = 5  # overlapping compound-return window


def _compound(returns: pd.Series | pd.DataFrame, k: int):
    return (1 + returns).rolling(k).apply(np.prod, raw=True) - 1


def _factor_returns(conn: sqlite3.Connection) -> pd.DataFrame:
    """Daily factor returns, each shifted by its publication lag."""
    cols = {}
    for label, (series, lag) in FACTORS.items():
        s = bm.load_series(conn, series)
        if not s.empty:
            cols[label] = s.pct_change().shift(lag)
    return pd.DataFrame(cols).dropna(how="all")


def fund_factor_model(conn: sqlite3.Connection, code: str,
                      days: int = 252, min_obs: int = 60) -> dict:
    """Fit the factor model for one fund over the trailing window."""
    code = code.upper()
    nav = pd.read_sql_query(
        "SELECT date, price FROM prices WHERE code = ? ORDER BY date",
        conn, params=(code,), parse_dates=["date"]).set_index("date")["price"]
    nav = nav.replace(0, np.nan).dropna()
    if nav.empty:
        raise KeyError(f"No data for fund {code}")

    fund_ret = nav.pct_change().dropna().tail(days)
    fx = _factor_returns(conn)
    daily = pd.concat([fund_ret.rename("fund"), fx], axis=1).dropna()
    if len(daily) < min_obs:
        raise ValueError(f"Only {len(daily)} overlapping observations "
                         f"for {code} (need {min_obs})")
    data = _compound(daily, K_DAYS).dropna()

    y = data["fund"].to_numpy()
    factor_names = [c for c in data.columns if c != "fund"]
    X = np.column_stack([np.ones(len(data))]
                        + [data[f].to_numpy() for f in factor_names])
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    r2 = 1 - resid.var() / y.var() if y.var() > 0 else np.nan
    alpha_daily = float(coef[0]) / K_DAYS  # intercept is per K-day period
    # alpha t-stat, same estimator as the batch path (all_factor_betas):
    # OLS SE with ~K variance inflation for the overlapping-return
    # serial correlation — conservative, and consistent across surfaces
    dof = max(len(y) - X.shape[1], 1)
    s2 = (resid @ resid) / dof * K_DAYS
    try:
        alpha_se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
        alpha_t = float(coef[0] / alpha_se) if alpha_se > 0 else float("nan")
    except np.linalg.LinAlgError:
        alpha_t = float("nan")

    # attribution over the same window (daily returns, full window)
    start, end = daily.index[0], daily.index[-1]
    window_nav = nav.loc[start:end]
    fund_total = float(window_nav.iloc[-1] / window_nav.iloc[0] - 1)
    contributions = {}
    for i, f in enumerate(factor_names):
        factor_total = float((1 + daily[f]).prod() - 1)
        contributions[f] = {
            "beta": round(float(coef[i + 1]), 3),
            "factor_return": round(factor_total, 4),
            "contribution": round(float(coef[i + 1]) * factor_total, 4),
        }
    explained = sum(c["contribution"] for c in contributions.values())

    title = conn.execute("SELECT title, category FROM funds WHERE code = ?",
                         (code,)).fetchone()
    return {
        "code": code,
        "title": title[0] if title else None,
        "category": title[1] if title else None,
        "window": f"{start.date()} .. {end.date()}",
        "n_obs": len(daily),
        "fund_return": round(fund_total, 4),
        "alpha_annual": round(alpha_daily * metrics.TRADING_DAYS, 4),
        "alpha_t": round(alpha_t, 2) if np.isfinite(alpha_t) else None,
        "r_squared": round(float(r2), 3),
        "factors": contributions,
        "unexplained_return": round(fund_total - explained, 4),
    }


def all_factor_betas(conn: sqlite3.Connection, days: int = 252,
                     min_obs: int = 60) -> pd.DataFrame:
    """Betas + alpha + R^2 for every fund with enough history (vectorized
    enough for ~2k funds)."""
    prices = metrics.load_prices(conn)
    returns = prices.pct_change(fill_method=None).tail(days)
    fx = _factor_returns(conn).reindex(returns.index)
    factor_names = list(fx.columns)

    returns_k = _compound(returns, K_DAYS)
    fx_k = _compound(fx, K_DAYS)

    rows = []
    base = np.column_stack([np.ones(len(fx_k))]
                           + [fx_k[f] for f in factor_names])
    for code in returns_k.columns:
        y = returns_k[code].to_numpy()
        mask = ~np.isnan(y) & ~np.isnan(base).any(axis=1)
        if mask.sum() < min_obs:
            continue
        X = base[mask]
        coef, _, _, _ = np.linalg.lstsq(X, y[mask], rcond=None)
        resid = y[mask] - X @ coef
        var = y[mask].var()
        # OLS standard errors. Overlapping K-day returns induce serial
        # correlation, so scale the naive variance by ~K (a crude
        # Hansen-Hodrick-style correction) — t-stats are conservative.
        dof = max(int(mask.sum()) - X.shape[1], 1)
        s2 = (resid @ resid) / dof * K_DAYS
        try:
            xtx_inv = np.linalg.inv(X.T @ X)
            alpha_se = np.sqrt(s2 * xtx_inv[0, 0])
            alpha_t = coef[0] / alpha_se if alpha_se > 0 else np.nan
        except np.linalg.LinAlgError:
            alpha_t = np.nan
        rows.append({
            "code": code,
            "alpha_annual": coef[0] / K_DAYS * metrics.TRADING_DAYS,
            "alpha_t": alpha_t,
            **{f"beta_{f}": coef[i + 1] for i, f in enumerate(factor_names)},
            "r_squared": 1 - resid.var() / var if var > 0 else np.nan,
            "n_obs": int(mask.sum()),
        })
    out = pd.DataFrame(rows).set_index("code")
    meta = pd.read_sql_query(
        "SELECT code, title, category FROM funds", conn).set_index("code")
    return out.join(meta)


def category_diagnostics(conn: sqlite3.Connection,
                         min_obs: int = 126) -> pd.DataFrame:
    """Does the factor model make economic sense per category? Mean
    betas and fit by category — a sanity table (equity should load on
    BIST, foreign on Nasdaq, gold funds on gold, money market on
    nothing)."""
    betas = all_factor_betas(conn, min_obs=min_obs)
    agg = betas.groupby("category").agg(
        funds=("r_squared", "size"),
        mean_r2=("r_squared", "mean"),
        beta_bist=("beta_bist100", "mean"),
        beta_gold=("beta_gold_try", "mean"),
        beta_usd=("beta_usdtry", "mean"),
        beta_nasdaq=("beta_nasdaq_try", "mean"),
        pct_sig_alpha=("alpha_t", lambda s: (s.abs() > 2).mean()),
    ).round(3)
    return agg.sort_values("funds", ascending=False)
