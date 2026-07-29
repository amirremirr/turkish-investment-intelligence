"""Experimental, descriptive momentum-exhaustion watch.

This is deliberately a risk-context flag, never a buy/sell recommendation.
It uses yesterday's completed daily bar and today's provider-reported open.
"""
from __future__ import annotations

import hashlib
import json
import pandas as pd


SIGNAL_VERSION = "exhaustion-v1"


def _prior_up_streak(closes: pd.Series) -> int:
    returns = closes.pct_change().dropna().to_list()
    streak = 0
    for value in reversed(returns):
        if value <= 0:
            break
        streak += 1
    return streak


def build_watch(history: pd.DataFrame, live: pd.DataFrame, limit: int = 10) -> list[dict]:
    """Return crowded prior-day events opening >1% higher today.

    ``history`` has ticker/date/close/volume/title and ends at the last
    official close; ``live`` is indexed by ticker with ``open`` and title.
    Missing or non-positive prices are excluded rather than inferred.
    """
    rows: list[dict] = []
    for ticker, frame in history.groupby("ticker"):
        frame = frame.sort_values("date")
        if len(frame) < 22 or ticker not in live.index:
            continue
        yesterday, prior = frame.iloc[-1], frame.iloc[-21:-1]
        prev_close = frame.iloc[-2].close
        opening = live.loc[ticker, "open"]
        if pd.isna(opening) or opening <= 0 or prev_close <= 0:
            continue
        daily_return = yesterday.close / prev_close - 1
        normal_turnover = (prior.close * prior.volume).median()
        shock = yesterday.close * yesterday.volume / normal_turnover if normal_turnover > 0 else float("nan")
        prior_5d = frame.iloc[-2].close / frame.iloc[-7].close - 1
        streak = _prior_up_streak(frame.iloc[:-1].close)
        gap = opening / yesterday.close - 1
        if not (daily_return >= .07 and shock >= 2 and gap >= .01):
            continue
        reasons = ["prior-day gain ≥7%", "turnover ≥2x normal", "opening gap ≥1%"]
        if prior_5d >= .15:
            reasons.append("prior 5-session rise ≥15%")
        if streak >= 2:
            reasons.append("multiple prior up days")
        rows.append({
            "ticker": ticker, "title": str(live.loc[ticker].get("title") or "")[:40],
            "previous_close_adjusted": round(float(yesterday.close), 4),
            "opening_price": round(float(opening), 2),
            "opening_gap_pct": round(float(gap * 100), 2),
            "previous_day_return_pct": round(float(daily_return * 100), 2),
            "turnover_shock": round(float(shock), 2),
            "prior_5d_return_pct": round(float(prior_5d * 100), 2),
            "prior_positive_days": streak, "reasons": reasons,
            "severity": len(reasons),
        })
    return sorted(rows, key=lambda r: (r["severity"], r["opening_gap_pct"]), reverse=True)[:limit]


def ledger_rows(candidates: list[dict], as_of_timestamp: str) -> list[dict]:
    """Create immutable, idempotent research-observation rows."""
    signal_date = as_of_timestamp[:10]
    rows = []
    for candidate in candidates:
        key = f"{SIGNAL_VERSION}|{signal_date}|{candidate['ticker']}|avoid_chase"
        rows.append({
            "signal_id": hashlib.sha256(key.encode()).hexdigest(),
            "signal_version": SIGNAL_VERSION,
            "as_of_timestamp": as_of_timestamp,
            "signal_date": signal_date,
            "ticker": candidate["ticker"],
            "state": "research",
            "classification": "avoid_chase",
            "features_json": json.dumps(candidate, ensure_ascii=False, sort_keys=True),
            "source_quality": "delayed_daily_open",
            "data_cutoff": as_of_timestamp,
            "created_at": as_of_timestamp,
        })
    return rows
