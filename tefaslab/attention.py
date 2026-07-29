"""Daily BIST attention--momentum research study.

The module intentionally separates a *signal observed at a day's close* from
the next session's executable open-to-close return.  It is a research tool,
not a trading or recommendation engine.  See ``docs/research/attention-
momentum.md`` for the pre-specified assumptions and scenario family.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AttentionScenario:
    """A fully stated daily formation rule; all values are known by close t."""

    name: str
    description: str
    top_n: int
    return_rank_min: float = 0.90
    return_min: float | None = 0.02
    return_max: float | None = 0.09
    turnover_shock_min: float | None = 2.0
    close_strength_min: float | None = 0.75
    max_previous_positive_days: int | None = 3
    score: str = "attention"


DEFAULT_SCENARIOS = (
    AttentionScenario(
        "attention_top10", "Pre-specified primary: broad attention with moderate momentum", 10),
    AttentionScenario(
        "attention_top5", "More concentrated primary rule", 5),
    AttentionScenario(
        "attention_top20", "More diversified primary rule", 20),
    AttentionScenario(
        "high_turnover_top10", "Primary rule requiring at least 4x normal turnover", 10,
                          turnover_shock_min=4.0),
    AttentionScenario(
        "return_only_top10", "Return-rank control; no attention confirmation", 10,
                          return_min=None, return_max=None,
                          turnover_shock_min=None, close_strength_min=None,
                          max_previous_positive_days=None, score="return"),
    AttentionScenario(
        "extreme_winners_top10", "High-return comparison group, potentially exhausted", 10,
                          return_rank_min=0.90, return_min=0.075, return_max=None,
                          turnover_shock_min=None, close_strength_min=None,
                          max_previous_positive_days=None, score="return"),
)


def _previous_positive_streak(ret: pd.Series) -> pd.Series:
    """Consecutive positive days ending before each row (no forward data)."""
    positive = ret.fillna(0).gt(0)
    groups = (~positive).cumsum()
    inclusive = positive.groupby(groups).cumcount().add(1).where(positive, 0)
    return inclusive.shift(1).fillna(0)


def _normal_one_sided_p(t_stat: float) -> float:
    if not np.isfinite(t_stat):
        return np.nan
    return float(0.5 * math.erfc(t_stat / math.sqrt(2)))


def _nw_mean(values: pd.Series, lags: int = 1) -> tuple[float, float, float]:
    """Mean, Newey--West standard error and one-sided t statistic."""
    x = values.dropna().to_numpy(dtype=float)
    n = len(x)
    if n < 30:
        return np.nan, np.nan, np.nan
    mean = float(x.mean())
    u = x - mean
    long_run = float(u @ u / n)
    for lag in range(1, min(int(lags), n - 1) + 1):
        weight = 1 - lag / (lags + 1)
        gamma = float(u[lag:] @ u[:-lag] / n)
        long_run += 2 * weight * gamma
    se = math.sqrt(max(long_run, 0) / n)
    return mean, se, mean / se if se > 0 else np.nan


def _block_bootstrap_ci(values: pd.Series, block: int, draws: int,
                        seed: int) -> tuple[float, float]:
    """Moving-block bootstrap CI for the mean; deterministic for a snapshot."""
    x = values.dropna().to_numpy(dtype=float)
    n = len(x)
    if n < 30:
        return np.nan, np.nan
    block = max(1, min(int(block), n))
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    for i in range(draws):
        starts = rng.integers(0, n, size=math.ceil(n / block))
        sample = np.concatenate([np.take(x, np.arange(s, s + block) % n)
                                 for s in starts])[:n]
        means[i] = sample.mean()
    return tuple(float(v) for v in np.quantile(means, [0.025, 0.975]))


def _max_drawdown(values: pd.Series) -> float:
    wealth = (1 + values.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min()) if not wealth.empty else np.nan


def _longest_losing_streak(values: pd.Series) -> int:
    longest = current = 0
    for value in values.dropna():
        current = current + 1 if value < 0 else 0
        longest = max(longest, current)
    return longest


def _summary(values: pd.Series, abnormal: pd.Series, cost_bps: int,
             horizon: int, seed: int) -> dict:
    net = values - cost_bps / 10_000
    x = net.dropna()
    mean, nw_se, nw_t = _nw_mean(x, lags=max(1, horizon))
    ci_low, ci_high = _block_bootstrap_ci(x, block=max(1, horizon), draws=400,
                                          seed=seed)
    if x.empty:
        return {"observations": 0}
    worst = x.nsmallest(max(1, math.ceil(len(x) * 0.05)))
    return {
        "observations": int(len(x)), "mean_net_return": mean,
        "median_net_return": float(x.median()), "std_return": float(x.std(ddof=1)),
        "win_rate": float((x > 0).mean()),
        "mean_abnormal_return": float(abnormal.reindex(x.index).mean()),
        "nw_se": nw_se, "nw_t": nw_t, "one_sided_p": _normal_one_sided_p(nw_t),
        "bootstrap_ci_low": ci_low, "bootstrap_ci_high": ci_high,
        "worst_5pct_mean": float(worst.mean()), "max_drawdown": _max_drawdown(x),
        "longest_losing_streak": _longest_losing_streak(x),
        "skew": float(x.skew()), "positive_months": float(
            (x.resample("ME").apply(lambda z: (1 + z).prod() - 1) > 0).mean()),
    }


def _benjamini_hochberg(pvalues: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=pvalues.index, dtype=float)
    valid = pvalues.dropna()
    if valid.empty:
        return out
    ordered = valid.sort_values()
    m = len(ordered)
    adjusted = ordered * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted.iloc[::-1])[::-1].clip(upper=1)
    out.loc[ordered.index] = adjusted
    return out


def _load_signals(conn: sqlite3.Connection, min_history: int,
                  min_turnover: float, start: str | None,
                  end: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    sql = """
        SELECT p.ticker, p.date, p.open, p.high, p.low, p.close, p.volume,
               COALESCE(s.sector, 'Unknown') AS sector
        FROM stock_prices p LEFT JOIN stocks s ON s.ticker=p.ticker
        WHERE p.open > 0 AND p.high > 0 AND p.low > 0 AND p.close > 0
          AND p.volume >= 0
    """
    params: list[str] = []
    if start:
        sql += " AND p.date >= ?"; params.append(start)
    if end:
        sql += " AND p.date <= ?"; params.append(end)
    prices = pd.read_sql_query(sql + " ORDER BY p.ticker, p.date", conn,
                               params=params, parse_dates=["date"])
    if prices.empty:
        raise ValueError("stock_prices has no valid OHLCV rows for this study")
    prices["turnover"] = prices["close"] * prices["volume"]
    grouped = prices.groupby("ticker", group_keys=False)
    prices["previous_close"] = grouped["close"].shift(1)
    prices["daily_return"] = prices["close"] / prices["previous_close"] - 1
    prices["prior_median_turnover"] = grouped["turnover"].transform(
        lambda s: s.rolling(20, min_periods=20).median().shift(1))
    prices["history_days"] = grouped.cumcount()
    prices["previous_positive_days"] = grouped["daily_return"].transform(
        _previous_positive_streak)
    prices["turnover_shock"] = prices["turnover"] / prices["prior_median_turnover"]
    prices["close_strength"] = np.where(
        prices["high"] > prices["low"],
        (prices["close"] - prices["low"]) / (prices["high"] - prices["low"]), np.nan)
    prices["eligible"] = (
        (prices["history_days"] >= min_history)
        & prices["daily_return"].notna()
        & (prices["prior_median_turnover"] >= min_turnover)
    )
    prices["market_return"] = prices["daily_return"].where(prices["eligible"]).groupby(prices["date"]).transform("mean")
    prices["relative_return"] = prices["daily_return"] - prices["market_return"]
    valid = prices["eligible"]
    for source, target in (("daily_return", "return_rank"),
                           ("turnover_shock", "turnover_rank"),
                           ("close_strength", "close_strength_rank"),
                           ("relative_return", "relative_return_rank")):
        prices[target] = prices[source].where(valid).groupby(prices["date"]).rank(pct=True)
    prices["attention_score"] = (
        0.35 * prices["return_rank"] + 0.30 * prices["turnover_rank"]
        + 0.20 * prices["close_strength_rank"] + 0.15 * prices["relative_return_rank"])
    market = prices.loc[prices["eligible"]].groupby("date").agg(
        market_intraday=("close", "size"),
        eligible_stocks=("ticker", "nunique"),
    )
    # The intraday market benchmark needs an open-to-close return, calculated
    # only from stocks valid at that session, never from future prices.
    prices["intraday_return"] = prices["close"] / prices["open"] - 1
    market["market_intraday"] = prices.loc[prices["eligible"]].groupby("date")["intraday_return"].mean()
    return prices, market


def _select(prices: pd.DataFrame, scenario: AttentionScenario) -> pd.DataFrame:
    mask = prices["eligible"] & (prices["return_rank"] >= scenario.return_rank_min)
    if scenario.return_min is not None:
        mask &= prices["daily_return"] >= scenario.return_min
    if scenario.return_max is not None:
        mask &= prices["daily_return"] <= scenario.return_max
    if scenario.turnover_shock_min is not None:
        mask &= prices["turnover_shock"] >= scenario.turnover_shock_min
    if scenario.close_strength_min is not None:
        mask &= prices["close_strength"] >= scenario.close_strength_min
    if scenario.max_previous_positive_days is not None:
        mask &= prices["previous_positive_days"] <= scenario.max_previous_positive_days
    selected = prices.loc[mask].copy()
    key = "attention_score" if scenario.score == "attention" else "return_rank"
    selected = selected.sort_values(["date", key, "ticker"], ascending=[True, False, True])
    selected = selected.groupby("date", group_keys=False).head(scenario.top_n).copy()
    selected["scenario"] = scenario.name
    return selected


def _attach_outcomes(events: pd.DataFrame, prices: pd.DataFrame,
                     horizons: tuple[int, ...]) -> pd.DataFrame:
    calendar = pd.Index(sorted(prices["date"].unique()))
    positions = {date: i for i, date in enumerate(calendar)}
    event = events.copy()
    event["entry_date"] = event["date"].map(
        lambda d: calendar[positions[d] + 1] if positions[d] + 1 < len(calendar) else pd.NaT)
    indexed = prices.set_index(["ticker", "date"])
    def lookup(column: str, dates: pd.Series) -> np.ndarray:
        key = pd.MultiIndex.from_arrays([event["ticker"], dates])
        return indexed[column].reindex(key).to_numpy()
    event["entry_open"] = lookup("open", event["entry_date"])
    event["entry_close"] = lookup("close", event["entry_date"])
    event["overnight_return"] = event["entry_open"] / event["close"] - 1
    event["open_to_close_1"] = event["entry_close"] / event["entry_open"] - 1
    event["close_to_close_1"] = event["entry_close"] / event["close"] - 1
    for horizon in horizons:
        exit_dates = event["date"].map(
            lambda d: calendar[positions[d] + horizon] if positions[d] + horizon < len(calendar) else pd.NaT)
        event[f"open_to_close_{horizon}"] = lookup("close", exit_dates) / event["entry_open"] - 1
    return event


def _portfolio_rows(events: pd.DataFrame, market: pd.DataFrame,
                    scenarios: tuple[AttentionScenario, ...], horizons: tuple[int, ...],
                    costs_bps: tuple[int, ...], split: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    outcome_cols = ["overnight_return", "open_to_close_1", "close_to_close_1"] + [
        f"open_to_close_{h}" for h in horizons if h != 1]
    daily_rows, rows = [], []
    for scenario_i, scenario in enumerate(scenarios):
        subset = events[events["scenario"] == scenario.name]
        for outcome in outcome_cols:
            daily = subset.groupby("date").agg(
                gross_return=(outcome, "mean"), selected=("ticker", "size"),
                executed=(outcome, lambda s: int(s.notna().sum())),
            )
            daily["scenario"] = scenario.name
            daily["outcome"] = outcome
            daily["market_return"] = market["market_intraday"].reindex(
                pd.to_datetime(daily.index)).to_numpy() if outcome == "open_to_close_1" else np.nan
            daily["abnormal_return"] = daily["gross_return"] - daily["market_return"]
            daily_rows.append(daily.reset_index(names="signal_date"))
            horizon = int(outcome.rsplit("_", 1)[-1]) if outcome.startswith("open_to_close_") else 1
            for cost in costs_bps:
                for sample, frame in (("discovery", daily[daily.index < pd.Timestamp(split)]),
                                      ("validation", daily[daily.index >= pd.Timestamp(split)]),
                                      ("full", daily)):
                    result = _summary(frame["gross_return"], frame["abnormal_return"], cost,
                                      horizon, seed=10_000 + scenario_i * 100 + cost + horizon)
                    rows.append({"scenario": scenario.name, "description": scenario.description,
                                 "outcome": outcome, "horizon_sessions": horizon,
                                 "round_trip_cost_bps": cost, "sample": sample,
                                 "average_selected": float(frame["selected"].mean()) if len(frame) else np.nan,
                                 "average_executed": float(frame["executed"].mean()) if len(frame) else np.nan,
                                 **result})
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["fdr_q_value"] = _benjamini_hochberg(summary["one_sided_p"])
        summary["research_status"] = "exploratory"
    return summary, pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()


def _attention_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Descriptive return/turnover matrix; not a separate trading claim."""
    frame = prices[prices["eligible"]].copy()
    calendar = pd.Index(sorted(frame["date"].unique()))
    pos = {d: i for i, d in enumerate(calendar)}
    frame["entry_date"] = frame["date"].map(
        lambda d: calendar[pos[d] + 1] if pos[d] + 1 < len(calendar) else pd.NaT)
    next_rows = frame[["ticker", "date", "open", "close"]].rename(
        columns={"date": "entry_date", "open": "entry_open", "close": "entry_close"})
    frame = frame.merge(next_rows, on=["ticker", "entry_date"], how="left")
    frame["next_open_to_close"] = frame["entry_close"] / frame["entry_open"] - 1
    frame["return_bucket"] = pd.cut(frame["daily_return"],
                                    [-np.inf, .02, .04, .07, .09, np.inf],
                                    labels=["<2%", "2-4%", "4-7%", "7-9%", "9%+"])
    frame["turnover_bucket"] = pd.cut(frame["turnover_shock"],
                                      [-np.inf, 1, 2, 4, np.inf],
                                      labels=["<=1x", "1-2x", "2-4x", ">4x"])
    return frame.groupby(["return_bucket", "turnover_bucket"], observed=False).agg(
        events=("ticker", "size"), mean_next_open_to_close=("next_open_to_close", "mean"),
        median_next_open_to_close=("next_open_to_close", "median"),
        win_rate=("next_open_to_close", lambda s: (s > 0).mean()),
    ).reset_index()


def run_attention_momentum_study(
        conn: sqlite3.Connection, *, start: str | None = None, end: str | None = None,
        min_history: int = 60, min_turnover: float = 1_000_000,
        split: str = "2026-01-01", horizons: tuple[int, ...] = (1, 2, 3, 5, 10, 21),
        costs_bps: tuple[int, ...] = (0, 25, 50, 100),
        scenarios: tuple[AttentionScenario, ...] = DEFAULT_SCENARIOS) -> dict[str, object]:
    """Run the complete daily attention--momentum scenario family.

    The primary executable outcome is next-session ``open_to_close_1``. All
    other outcomes are diagnostics; close-to-open is expressly theoretical.
    """
    prices, market = _load_signals(conn, min_history, min_turnover, start, end)
    selected = pd.concat([_select(prices, s) for s in scenarios], ignore_index=True)
    events = _attach_outcomes(selected, prices, horizons) if not selected.empty else selected
    summary, daily = _portfolio_rows(events, market, scenarios, horizons, costs_bps, split)
    metadata = {
        "research_status": "exploratory", "source": "Yahoo daily BIST OHLCV",
        "start": str(prices["date"].min().date()), "end": str(prices["date"].max().date()),
        "rows": int(len(prices)), "tickers": int(prices["ticker"].nunique()),
        "min_history_sessions": min_history, "minimum_prior_median_turnover_try": min_turnover,
        "holdout_split": split, "horizons": list(horizons), "costs_bps": list(costs_bps),
        "scenarios": [asdict(s) for s in scenarios],
        "primary_outcome": "open_to_close_1", "known_limits": [
            "Daily bars cannot test intraday exits, auction fill probability, or bid-ask spreads.",
            "Yahoo OHLCV can contain BIST gaps or adjusted-price anomalies.",
            "The historical ticker universe lacks delisted securities and therefore has survivorship bias.",
            "A limit-up close is not assumed executable; no order-book data is available.",
        ],
    }
    return {"summary": summary, "daily": daily, "events": events,
            "attention_matrix": _attention_matrix(prices), "metadata": metadata}


def write_attention_outputs(result: dict[str, object], directory: str | Path) -> Path:
    """Write transparent CSV/Markdown artifacts for an immutable research run."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    events = result["events"]
    matrix = result["attention_matrix"]
    metadata = result["metadata"]
    assert isinstance(summary, pd.DataFrame) and isinstance(events, pd.DataFrame)
    assert isinstance(matrix, pd.DataFrame) and isinstance(metadata, dict)
    summary.to_csv(out / "attention_momentum_summary.csv", index=False)
    events.to_csv(out / "attention_momentum_events.csv", index=False)
    matrix.to_csv(out / "attention_momentum_matrix.csv", index=False)
    primary = summary[(summary["outcome"] == "open_to_close_1")
                      & (summary["round_trip_cost_bps"] == 50)
                      & (summary["sample"] == "validation")]
    lines = ["# Daily attention--momentum study", "", "Status: **exploratory**.", "",
             "## Run metadata", ""]
    lines += [f"- **{key}**: {value}" for key, value in metadata.items() if key != "scenarios"]
    lines += ["", "## Primary executable outcome", "",
              "Signal at close *t*; buy at open *t+1*; sell at close *t+1*. "
              "Returns below include a 50 bps round-trip cost assumption.", "",
              primary.to_markdown(index=False) if not primary.empty else "No executable observations.",
              "", "See `attention_momentum_summary.csv` for every pre-specified scenario, cost and horizon."]
    path = out / "attention_momentum_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
