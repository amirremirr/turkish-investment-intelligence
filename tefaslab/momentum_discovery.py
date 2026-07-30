"""Bounded historical search for *candidate* next-session momentum conditions.

This module is intentionally a discovery tool, not a signal generator. It
reports its complete fixed condition family, uses daily portfolios rather than
pooled stock rows, applies a 50 bps cost sensitivity, and controls the false
discovery rate. A favourable row still needs prospective data before it can be
considered for the live collector.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .attention import (_attach_outcomes, _benjamini_hochberg, _block_bootstrap_ci,
                        _load_signals, _normal_one_sided_p, _nw_mean)


DISCOVERY_COST_BPS = 50
MIN_PORTFOLIO_DAYS = 30


def _bucket_features(events: pd.DataFrame) -> pd.DataFrame:
    frame = events.copy()
    frame["return_bucket"] = pd.cut(
        frame["daily_return"], [.02, .04, .07, .09, np.inf], right=False,
        labels=["2-4%", "4-7%", "7-9%", "9%+"])
    frame["turnover_bucket"] = pd.cut(
        frame["turnover_shock"], [-np.inf, .5, 1, 2, 4, np.inf], right=False,
        labels=["<0.5x", "0.5-1x", "1-2x", "2-4x", "4x+"])
    frame["gap_bucket"] = pd.cut(
        frame["overnight_return"], [-np.inf, 0, .005, .01, .02, np.inf], right=False,
        labels=["negative", "0 to +0.5%", "+0.5 to +1%", "+1 to +2%", "+2%+"])
    frame["close_strength_bucket"] = pd.cut(
        frame["close_strength"], [-np.inf, .6, .75, np.inf], right=False,
        labels=["below 0.60", "0.60-0.75", "0.75+"])
    frame["pre_5d_bucket"] = pd.cut(
        frame["pre_signal_5d_return"], [-np.inf, 0, .05, .15, np.inf], right=False,
        labels=["flat/down", "0-5%", "5-15%", "15%+"])
    frame["prior_up_days_bucket"] = pd.cut(
        frame["previous_positive_days"], [-np.inf, 1, 2, np.inf], right=False,
        labels=["0", "1", "2+"])
    return frame


def _daily_condition_rows(frame: pd.DataFrame, condition: str,
                          family: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    daily = frame.groupby("date", observed=True).agg(
        gross_return=("open_to_close_1", "mean"), events=("ticker", "size"))
    daily = daily.dropna(subset=["gross_return"])
    daily["condition"] = condition
    daily["family"] = family
    return daily.reset_index(names="signal_date")


def _summary_rows(daily: pd.DataFrame, split: str) -> pd.DataFrame:
    rows: list[dict] = []
    split_at = pd.Timestamp(split)
    for (family, condition), group in daily.groupby(["family", "condition"], observed=True):
        group = group.set_index("signal_date").sort_index()
        for sample, values in (
            ("before configured split", group[group.index < split_at]),
            ("after configured split", group[group.index >= split_at]),
            ("full historical discovery", group),
        ):
            net = values["gross_return"] - DISCOVERY_COST_BPS / 10_000
            mean, se, t_stat = _nw_mean(net, lags=1)
            low, high = _block_bootstrap_ci(net, block=1, draws=400, seed=42)
            rows.append({
                "family": family, "condition": condition, "sample": sample,
                "portfolio_days": len(values), "stock_events": int(values["events"].sum()),
                "average_names": float(values["events"].mean()) if len(values) else np.nan,
                "gross_mean": float(values["gross_return"].mean()) if len(values) else np.nan,
                "net_mean_after_50bps": mean,
                "net_median_after_50bps": float(net.median()) if len(net) else np.nan,
                "win_rate_after_50bps": float((net > 0).mean()) if len(net) else np.nan,
                "nw_se": se, "nw_t": t_stat, "one_sided_p": _normal_one_sided_p(t_stat),
                "bootstrap_95_low": low, "bootstrap_95_high": high,
            })
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    summary["fdr_q_value"] = _benjamini_hochberg(summary["one_sided_p"])
    summary["provisional_candidate"] = (
        (summary["sample"] == "full historical discovery")
        & (summary["portfolio_days"] >= MIN_PORTFOLIO_DAYS)
        & (summary["net_mean_after_50bps"] > 0)
        & (summary["net_median_after_50bps"] > 0)
        & (summary["fdr_q_value"] <= .10)
    )
    return summary.sort_values(
        ["provisional_candidate", "fdr_q_value", "net_median_after_50bps"],
        ascending=[False, True, False], na_position="last").reset_index(drop=True)


def run_momentum_discovery(conn: sqlite3.Connection, *, start: str | None = None,
                           end: str | None = None, split: str = "2026-01-01") -> dict[str, object]:
    """Evaluate the frozen, 64-row next-open-to-close discovery family.

    Formation needs a liquid stock with a positive 2%+ prior-day move. Each
    row is either a return bucket alone or that same bucket paired with one
    interpretable condition available no later than the next session's open.
    """
    prices, _ = _load_signals(conn, 60, 10_000_000, start, end)
    base = prices.loc[prices["eligible"] & (prices["daily_return"] >= .02)].copy()
    events = _attach_outcomes(base, prices, (1,)).dropna(subset=["open_to_close_1"])
    events = _bucket_features(events)

    condition_rows: list[pd.DataFrame] = []
    for ret in events["return_bucket"].dropna().cat.categories:
        selected = events[events["return_bucket"] == ret]
        condition_rows.append(_daily_condition_rows(selected, f"prior-day return {ret}", "return only"))
        for column, label in (
            ("turnover_bucket", "turnover"), ("gap_bucket", "opening gap"),
            ("close_strength_bucket", "close strength"),
            ("pre_5d_bucket", "prior 5-day move"),
            ("prior_up_days_bucket", "prior up days"),
        ):
            for bucket in events[column].dropna().cat.categories:
                pair = selected[selected[column] == bucket]
                condition_rows.append(_daily_condition_rows(
                    pair, f"prior-day return {ret}; {label} {bucket}",
                    f"return + {label}"))
    daily = pd.concat([r for r in condition_rows if not r.empty], ignore_index=True)
    summary = _summary_rows(daily, split)
    candidates = summary[summary["provisional_candidate"]].copy()
    metadata = {
        "study_id": "momentum-discovery",
        "study_title": "Bounded momentum-condition discovery",
        "research_status": "historical discovery only; prospective validation required",
        "source": "Yahoo daily BIST OHLCV",
        "formation": "Prior close, then next-session open-to-close outcome.",
        "base_universe": "At least 60 prior sessions, TRY 10m prior-20-session median turnover, prior-day return at least 2%.",
        "condition_family": "Return bucket alone plus return bucket paired with exactly one of turnover, opening gap, close strength, prior 5-day move, or prior up-day count.",
        "cost": f"{DISCOVERY_COST_BPS} bps round-trip sensitivity",
        "minimum_portfolio_days": MIN_PORTFOLIO_DAYS,
        "multiple_testing": "Benjamini-Hochberg FDR across every row and historical segment in the output.",
        "configured_split": split,
        "candidate_rule": "Positive mean and median after 50 bps, >=30 independent portfolio days, and FDR q <= 0.10. This is a triage rule, not validation.",
        "prospective_rule": "No row becomes a signal. A separately approved frozen cohort must collect future outcomes before any promotion.",
    }
    return {"summary": summary, "daily": daily, "events": events, "candidates": candidates,
            "metadata": metadata}


def write_momentum_discovery_outputs(result: dict[str, object], directory: str | Path) -> Path:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    daily = result["daily"]
    events = result["events"]
    candidates = result["candidates"]
    metadata = result["metadata"]
    assert isinstance(summary, pd.DataFrame) and isinstance(daily, pd.DataFrame)
    assert isinstance(events, pd.DataFrame) and isinstance(candidates, pd.DataFrame)
    assert isinstance(metadata, dict)
    summary.to_csv(out / "momentum_discovery_summary.csv", index=False)
    daily.to_csv(out / "momentum_discovery_daily_portfolios.csv", index=False)
    events.to_csv(out / "momentum_discovery_events.csv", index=False)
    candidates.to_csv(out / "momentum_discovery_provisional_candidates.csv", index=False)
    lines = ["# Bounded momentum-condition discovery", "",
             "Status: **historical discovery only; no trading signal is produced**.", "",
             "## Fixed method", ""]
    lines += [f"- **{key}**: {value}" for key, value in metadata.items()]
    lines += ["", "## Provisional candidates", "",
              candidates.to_markdown(index=False) if not candidates.empty else
              "No condition passed the declared historical triage rule.",
              "", "## Files", "",
              "- `momentum_discovery_summary.csv`: every tested condition and segment",
              "- `momentum_discovery_daily_portfolios.csv`: daily equal-weight portfolio returns",
              "- `momentum_discovery_events.csv`: every eligible stock event",
              "- `momentum_discovery_provisional_candidates.csv`: rows passing the strict historical triage rule",
              "", "Any positive row is still a discovery result. It must be frozen and tested on future sessions before it may be treated as evidence."]
    path = out / "momentum_discovery_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
