"""Statistical-rigor layer — the gate a finding must pass before it is
cited outside this workstation.

The research surface (research.py, factors.py) reports naive t-stats on
single studies. That is fine for exploration and wrong for citation.
This module adds the four corrections that separate "I noticed a
pattern" from "this survives scrutiny":

  1. Multiple-testing control on the cross-section of fund alphas.
     Scanning ~500 funds at p<0.05 yields ~25 "significant" alphas by
     chance alone. Bonferroni (family-wise) and Benjamini-Hochberg (FDR)
     say how many survive once you account for the search.

  2. A cash-rate hurdle + mandate-aware benchmark per category. The
     4-factor model has no risk-free factor, so in a 45%-rate regime a
     money-market fund's deposit yield reads as huge "alpha". Judging
     each category against its mandate benchmark (equity->BIST, cash
     funds->deposit rate) removes that artefact.

  3. AUM-weighted category returns next to the equal-weighted average —
     what the representative *lira* earned vs the representative *fund*.

  4. A fund-level panel (fund fixed effects, date-clustered SE) for the
     performance-chasing result, replacing one category-aggregate time
     series with ~all funds and standard errors robust to the common
     weekly market shock.

numpy-only, no scipy. Two-sided p-values use a normal approximation,
accurate at the hundreds of degrees of freedom here and — like the ~K
overlap inflation already baked into alpha_t — erring conservative.
"""

from __future__ import annotations

import math
import sqlite3

import numpy as np
import pandas as pd

from . import benchmarks as bm
from . import factors, flows, metrics

TRADING_DAYS = metrics.TRADING_DAYS

# |daily fund return| beyond this is a restructuring/split/reset artefact
# (the tiny-"özel"-fund fake-jump trap), not performance — mask it before
# aggregating, the same spirit as the flow module's NAV-move guard.
MAX_DAILY_MOVE = 0.25

# Each fund category judged against the benchmark its mandate implies.
# "CASH" = the deposit-rate hurdle (no tradable index for that mandate,
# or a flexible mandate for which a single equity benchmark is wrong).
# Honest gaps: no bond total-return index (Debt -> cash hurdle) and no
# participation index (Participation -> cash hurdle).
MANDATE_BENCHMARK = {
    "Equity Turkey": "bist100",
    "Foreign Equity": "nasdaq_try",
    "Precious Metals": "gold_try_gram",
    "Money Market": "CASH",
    "Debt": "CASH",
    "Participation": "CASH",
    "Variable": "CASH",
    "Mixed": "CASH",
    "Hedge (Serbest)": "CASH",
    "Fund of Funds": "CASH",
    "Other": "CASH",
}


# ----------------------------------------------------- multiple testing

def _norm_sf(z: np.ndarray) -> np.ndarray:
    """Upper-tail of the standard normal, element-wise."""
    return 0.5 * np.array([math.erfc(v / math.sqrt(2)) for v in np.atleast_1d(z)])


def two_sided_p(t) -> np.ndarray:
    """Two-sided p-value(s) for t-stat(s) under a normal approximation."""
    return 2.0 * _norm_sf(np.abs(np.asarray(t, float)))


def bonferroni(pvals, alpha: float = 0.05) -> tuple[np.ndarray, float]:
    """Family-wise control: reject where p <= alpha/m."""
    p = np.asarray(pvals, float)
    thresh = alpha / max(len(p), 1)
    return p <= thresh, float(thresh)


def benjamini_hochberg(pvals, alpha: float = 0.05) -> tuple[np.ndarray, float]:
    """Benjamini-Hochberg step-up FDR control. Returns (reject_mask,
    p_threshold). Reject every hypothesis with p <= the largest p_(k)
    satisfying p_(k) <= (k/m)*alpha."""
    p = np.asarray(pvals, float)
    m = len(p)
    if m == 0:
        return np.zeros(0, bool), 0.0
    order = np.argsort(p)
    ranked = p[order]
    crit = (np.arange(1, m + 1) / m) * alpha
    below = np.where(ranked <= crit)[0]
    if len(below) == 0:
        return np.zeros(m, bool), 0.0
    pth = ranked[below.max()]
    return p <= pth, float(pth)


def _cash_factor(conn) -> pd.DataFrame:
    """Daily risk-free accrual as a factor column, so a fund that merely
    earns the deposit rate loads on cash (beta~1) instead of showing the
    rate as alpha."""
    r = bm.load_series(conn, "deposit_3m")            # annualized %
    full = pd.date_range(r.index.min(), r.index.max(), freq="D")
    r = r.reindex(r.index.union(full)).sort_index().ffill()
    daily = (1 + r / 100.0) ** (1 / TRADING_DAYS) - 1
    return daily.to_frame("cash")


def alpha_gate(conn: sqlite3.Connection, fdr: float = 0.05,
               min_obs: int = 126) -> tuple[dict, pd.DataFrame]:
    """Multiple-testing gate on factor-model alpha across all funds.

    The factor model is augmented with a cash factor and restructuring
    jumps are clipped, so 'alpha' is genuine outperformance, not the
    deposit rate or a NAV reset. Returns a summary dict and the funds
    whose alpha survives FDR control — the only alphas defensible to
    cite as skill."""
    betas = factors.all_factor_betas(conn, min_obs=min_obs,
                                     extra_factors=_cash_factor(conn),
                                     clip_returns=MAX_DAILY_MOVE)
    betas = betas[np.isfinite(betas["alpha_t"])].copy()
    p = two_sided_p(betas["alpha_t"].to_numpy())
    betas["p_value"] = p
    nominal = p < 0.05
    bh_rej, bh_th = benjamini_hochberg(p, fdr)
    bonf_rej, bonf_th = bonferroni(p, 0.05)
    betas["sig_nominal"] = nominal
    betas["sig_fdr"] = bh_rej
    betas["sig_bonferroni"] = bonf_rej

    summary = {
        "n_funds_tested": int(len(betas)),
        "nominal_sig_0.05": int(nominal.sum()),
        "expected_false_pos": round(0.05 * len(betas), 1),
        "fdr_survivors": int(bh_rej.sum()),
        "fdr_threshold_p": round(bh_th, 5),
        "bonferroni_survivors": int(bonf_rej.sum()),
    }
    cols = ["title", "category", "alpha_annual", "alpha_t", "p_value",
            "r_squared", "n_obs", "sig_bonferroni"]
    survivors = (betas[bh_rej].sort_values("alpha_t", key=lambda s: s.abs(),
                                           ascending=False)[cols])
    return summary, survivors


# ------------------------------------------- AUM-weighted category returns

def _aum_matrix(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT code, date, aum FROM prices WHERE aum IS NOT NULL",
        conn, parse_dates=["date"])
    return df.pivot_table(index="date", columns="code",
                          values="aum").sort_index()


def _annualize(daily: pd.Series, min_days: int = 60) -> float:
    d = daily.dropna()
    if len(d) < min_days:
        return float("nan")
    return float((1 + d).prod() ** (TRADING_DAYS / len(d)) - 1)


def _category_codes(conn) -> pd.Series:
    return pd.read_sql_query(
        "SELECT code, category FROM funds", conn).set_index("code")["category"]


def _clean(rets: pd.DataFrame) -> pd.DataFrame:
    """Mask restructuring/reset artefacts before aggregating returns."""
    return rets.mask(rets.abs() > MAX_DAILY_MOVE)


def _weighted_daily(rets: pd.DataFrame, aum: pd.DataFrame,
                    codes: list[str]) -> tuple[pd.Series, pd.Series]:
    """Equal- and AUM-weighted daily category return. AUM weights are
    lagged one day so today's return is weighted by yesterday's size —
    no look-ahead."""
    r = _clean(rets[codes])
    w = aum.reindex(rets.index)[codes].ffill().shift(1)
    valid = r.notna() & w.notna()
    ew = r.where(valid).mean(axis=1)
    wsum = w.where(valid).sum(axis=1).replace(0, np.nan)
    vw = (r.where(valid) * w.where(valid)).sum(axis=1) / wsum
    return ew, vw


def category_returns(conn: sqlite3.Connection,
                     min_funds: int = 5) -> pd.DataFrame:
    """Per category: annualized equal-weighted vs AUM-weighted return.
    The gap is whether investor money sat in the funds that did better."""
    prices = metrics.load_prices(conn)
    rets = prices.pct_change(fill_method=None)
    aum = _aum_matrix(conn)
    cats = _category_codes(conn)
    rows = []
    for cat in cats.dropna().unique():
        codes = [c for c in rets.columns if cats.get(c) == cat]
        if len(codes) < min_funds:
            continue
        ew, vw = _weighted_daily(rets, aum, codes)
        ew_ann, vw_ann = _annualize(ew), _annualize(vw)
        rows.append({
            "category": cat, "n_funds": len(codes),
            "ann_ret_equal_wt": round(ew_ann, 4),
            "ann_ret_aum_wt": round(vw_ann, 4),
            "aum_minus_equal_pp": round((vw_ann - ew_ann) * 100, 2),
        })
    return (pd.DataFrame(rows).set_index("category")
            .sort_values("n_funds", ascending=False))


# ------------------------------------------------ mandate-aware benchmarks

def _bench_ret(conn, series: str, index: pd.Index) -> pd.Series:
    px = bm.load_series(conn, series)
    px = px.reindex(px.index.union(index)).sort_index().ffill().reindex(index)
    return px.pct_change()


def _cash_ret(conn, index: pd.Index, rate_series: str = "deposit_3m") -> pd.Series:
    """Per-trading-day accrual from an annualized deposit rate (%)."""
    r = bm.load_series(conn, rate_series)
    r = r.reindex(r.index.union(index)).sort_index().ffill().reindex(index)
    return (1 + r / 100.0) ** (1 / TRADING_DAYS) - 1


def mandate_excess(conn: sqlite3.Connection,
                   min_funds: int = 5) -> pd.DataFrame:
    """Each category's AUM-weighted return vs its MANDATE benchmark —
    the honest 'active value' bar (gross of fees, which we can't see)."""
    prices = metrics.load_prices(conn)
    rets = prices.pct_change(fill_method=None)
    aum = _aum_matrix(conn)
    cats = _category_codes(conn)
    rows = []
    for cat in cats.dropna().unique():
        codes = [c for c in rets.columns if cats.get(c) == cat]
        if len(codes) < min_funds:
            continue
        _, vw = _weighted_daily(rets, aum, codes)
        idx = vw.dropna().index
        if len(idx) < 60:
            continue
        bench = MANDATE_BENCHMARK.get(cat, "CASH")
        bret = (_cash_ret(conn, idx) if bench == "CASH"
                else _bench_ret(conn, bench, idx))
        fund_ann = _annualize(vw.reindex(idx))
        bench_ann = _annualize(bret)
        rows.append({
            "category": cat, "n_funds": len(codes), "benchmark": bench,
            "ann_ret_aum_wt": round(fund_ann, 4),
            "benchmark_ann": round(bench_ann, 4),
            "excess_pp": round((fund_ann - bench_ann) * 100, 2),
        })
    return (pd.DataFrame(rows).set_index("category")
            .sort_values("excess_pp", ascending=False))


# ------------------------------------------------------- fund-level panel

def _demean_by(v: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Subtract each group's mean (one-way fixed-effects transform)."""
    s = pd.Series(v)
    return (s - s.groupby(groups).transform("mean")).to_numpy()


def panel_fe_cluster(y, x, fund_ids, cluster_ids) -> dict:
    """Single-regressor panel OLS with one-way fixed effects (fund) and
    one-way cluster-robust SE (cluster_ids, e.g. week). The fixed
    effects absorb fund-level differences; the cluster correction makes
    the SE robust to the shared shock within each cluster."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    fund_ids = np.asarray(fund_ids)
    cluster_ids = np.asarray(cluster_ids)
    yt = _demean_by(y, fund_ids)
    xt = _demean_by(x, fund_ids)
    sxx = float((xt * xt).sum())
    if sxx == 0:
        return {"beta": float("nan"), "se": float("nan"), "t": float("nan"),
                "n": len(y), "n_funds": 0, "n_clusters": 0}
    beta = float((xt * yt).sum() / sxx)
    resid = yt - beta * xt

    clusters = np.unique(cluster_ids)
    meat = 0.0
    for g in clusters:
        m = cluster_ids == g
        sg = float((xt[m] * resid[m]).sum())
        meat += sg * sg
    n = len(y)
    n_funds = int(len(np.unique(fund_ids)))
    G = int(len(clusters))
    dof = max(n - n_funds - 1, 1)
    adj = (G / (G - 1)) * ((n - 1) / dof) if G > 1 else 1.0
    var = adj * meat / (sxx * sxx)
    se = math.sqrt(var) if var > 0 else float("nan")
    return {"beta": beta, "se": se,
            "t": beta / se if se and np.isfinite(se) else float("nan"),
            "n": n, "n_funds": n_funds, "n_clusters": G, "dof": dof}


def performance_chasing_panel(conn: sqlite3.Connection,
                              category: str = "Equity Turkey",
                              lookback: int = 63,
                              min_weeks: int = 20) -> tuple[dict, pd.DataFrame]:
    """Panel version of the performance-chasing result: weekly fund flow
    (% of AUM) on the fund's own lagged trailing return, fund FE, SE
    clustered by week. Positive beta = money follows a fund's own past
    performance, net of fund-level and common-week effects."""
    prices = metrics.load_prices(conn)
    cats = _category_codes(conn)
    codes = [c for c in prices.columns if cats.get(c) == category]
    aum = _aum_matrix(conn)
    flow_frame = flows.load_flow_frame(conn)

    recs = []
    for code in codes:
        nav = prices[code].dropna()
        if len(nav) < lookback + 40:
            continue
        ret = nav.pct_change()
        ret = ret.mask(ret.abs() > MAX_DAILY_MOVE)   # drop reset artefacts
        trailing = (1 + ret).rolling(lookback).apply(np.prod, raw=True) - 1
        f = flow_frame[flow_frame["code"] == code]
        if f.empty:
            continue
        f = f.set_index("date")["flow"]
        a = aum[code].reindex(nav.index).ffill() if code in aum.columns else None
        if a is None:
            continue
        flow_pct = (f.reindex(nav.index) / a) * 100.0        # % of AUM, daily
        wk_flow = flow_pct.resample("W").sum()
        wk_ret = (trailing * 100.0).resample("W").last().shift(1)  # lagged
        df = pd.concat([wk_flow.rename("flow"),
                        wk_ret.rename("ret")], axis=1).dropna()
        if len(df) < min_weeks:
            continue
        for wk, r in df.iterrows():
            recs.append((code, wk.value, float(r["flow"]), float(r["ret"])))

    panel = pd.DataFrame(recs, columns=["code", "week", "flow", "ret"])
    if panel.empty:
        return {"beta": float("nan"), "n": 0, "category": category,
                "lookback_days": lookback}, panel
    res = panel_fe_cluster(panel["flow"].to_numpy(), panel["ret"].to_numpy(),
                           panel["code"].to_numpy(), panel["week"].to_numpy())
    res.update({"category": category, "lookback_days": lookback})
    return res, panel


# ---------------------------------------------------------------- summary

def summary(conn: sqlite3.Connection) -> str:
    """A one-page robustness read on the headline findings — the memo
    you attach before citing anything."""
    gate, survivors = alpha_gate(conn)
    catret = category_returns(conn)
    mex = mandate_excess(conn)
    panel, _ = performance_chasing_panel(conn)

    L = ["# Findings robustness gate", ""]
    L += ["## 1. Fund alpha under multiple-testing control",
          f"- Funds tested: **{gate['n_funds_tested']}**",
          f"- Nominally significant (p<0.05): **{gate['nominal_sig_0.05']}** "
          f"(≈{gate['expected_false_pos']} expected by chance alone)",
          f"- Survive Benjamini-Hochberg FDR 5%: "
          f"**{gate['fdr_survivors']}** (p ≤ {gate['fdr_threshold_p']})",
          f"- Survive Bonferroni: **{gate['bonferroni_survivors']}**",
          ""]
    if not survivors.empty:
        L.append("FDR survivors — the only risk-adjusted signals worth "
                 "citing (a survivor with NEGATIVE alpha is robust "
                 "UNDERperformance, not skill; gross of fees):")
        L.append(survivors.head(12).round(3).to_string())
    else:
        L.append("_No fund's alpha survives FDR control — no individual "
                 "manager skill is citable on this sample._")
    L += ["", "## 2. Mandate-aware performance (AUM-weighted vs mandate)",
          "_Excess is RAW return vs the mandate benchmark, not "
          "risk-adjusted — a positive equity excess is largely beta>1 / "
          "small-cap tilt; the risk-adjusted view is the §1 alpha gate._",
          "", mex.round(3).to_string(), ""]
    L += ["## 3. AUM- vs equal-weighted category returns",
          "_Restructuring/reset jumps (>|25%|/day) clipped; a positive "
          "gap = investor money sat in the funds that did better._",
          "", catret.round(3).to_string(), ""]
    L += ["## 4. Performance chasing — fund panel (fund FE, week-clustered "
          "SE)",
          f"- {panel['category']}, {panel['lookback_days']}d trailing: "
          f"beta = {panel.get('beta', float('nan')):.3f}, "
          f"t = {panel.get('t', float('nan')):.2f} "
          f"(n={panel.get('n', 0)}, funds={panel.get('n_funds', 0)}, "
          f"week-clusters={panel.get('n_clusters', 0)})",
          "- reads as: does a fund's flow follow its OWN past return, once "
          "fund-level averages are removed and standard errors are made "
          "robust to the correlated weekly shock (so effective n is the "
          f"~{panel.get('n_clusters', 0)} weeks, not the fund-weeks)? "
          "Compare this |t| to the naive category-aggregate t before "
          "citing 'investors chase returns'.", ""]
    return "\n".join(L)
