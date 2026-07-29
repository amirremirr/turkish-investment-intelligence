"""Cloud intraday refresh — writes live quotes straight to Supabase.

Same computation as intraday.py (breadth, movers, index/FX snapshot from
~15-min-delayed Yahoo quotes) but reads its reference data from and
writes its result to the Supabase serving copy, so it can run on a
scheduled GitHub Actions cron instead of the user's PC. The public
Next.js app reads system_status['intraday'] and shows the live view.

No local SQLite and no 676 MB DB cache round-trip — it talks to Postgres
directly, which keeps a 15-minute cron cheap and fast.

Run:  python -m tefaslab intraday-cloud   (needs SUPABASE_DB_URL)
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text

from .publish import serving_url
from .exhaustion import build_watch, ledger_rows


def _clean(o):
    """Replace non-finite floats (inf/NaN — e.g. volume/0) with None so
    the payload is valid JSON. Python's json writes `Infinity`, which
    JavaScript's JSON.parse rejects; the JS web app reads this."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS signal_observations (
    signal_id TEXT PRIMARY KEY, signal_version TEXT NOT NULL,
    as_of_timestamp TEXT NOT NULL, signal_date TEXT NOT NULL, ticker TEXT NOT NULL,
    state TEXT NOT NULL, classification TEXT NOT NULL, features_json TEXT NOT NULL,
    source_quality TEXT NOT NULL, data_cutoff TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_trades (
    paper_trade_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL,
    status TEXT NOT NULL, entry_timestamp TEXT, intended_entry REAL,
    observed_entry REAL, exit_timestamp TEXT, observed_exit REAL,
    gross_return REAL, costs_bps REAL, net_return REAL,
    rejection_reason TEXT, source_quality TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signal_observations_date
ON signal_observations(signal_date, signal_version);
CREATE TABLE IF NOT EXISTS signal_intraday_bars (
    signal_id TEXT NOT NULL, ticker TEXT NOT NULL, bar_timestamp TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    provider TEXT NOT NULL, price_basis TEXT NOT NULL, retrieved_at TEXT NOT NULL,
    PRIMARY KEY (signal_id, bar_timestamp)
);
"""


def _ensure_signal_tables(engine) -> None:
    with engine.begin() as conn:
        for ddl in LEDGER_DDL.strip().split(";\n"):
            if ddl.strip():
                conn.execute(text(ddl))


def _record_signal_observations(engine, rows: list[dict]) -> int:
    """Idempotently persist research observations; never create trade claims."""
    _ensure_signal_tables(engine)
    with engine.begin() as conn:
        for row in rows:
            conn.execute(text("""
                INSERT INTO signal_observations
                (signal_id, signal_version, as_of_timestamp, signal_date, ticker,
                 state, classification, features_json, source_quality, data_cutoff, created_at)
                VALUES (:signal_id, :signal_version, :as_of_timestamp, :signal_date, :ticker,
                        :state, :classification, :features_json, :source_quality, :data_cutoff, :created_at)
                ON CONFLICT (signal_id) DO NOTHING
            """), row)
    return len(rows)


def _capture_signal_intraday_bars(engine, rows: list[dict], now: str) -> int:
    """Persist 5-minute bars only for prospective watch observations.

    Yahoo's intraday history is short-lived; capturing it at alert time is the
    only way to support a later opening-path study without pretending daily
    OHLCV answers intraday questions.
    """
    if not rows:
        return 0
    _ensure_signal_tables(engine)
    ids = {row["ticker"]: row["signal_id"] for row in rows}
    data = yf.download([f"{ticker}.IS" for ticker in ids], period="1d", interval="5m",
                       group_by="ticker", auto_adjust=True, progress=False, threads=True)
    bars = []
    for ticker, signal_id in ids.items():
        try:
            frame = data[f"{ticker}.IS"].dropna(how="all")
        except KeyError:
            continue
        for timestamp, bar in frame.iterrows():
            bars.append({"signal_id": signal_id, "ticker": ticker,
                         "bar_timestamp": str(timestamp), "open": float(bar["Open"]),
                         "high": float(bar["High"]), "low": float(bar["Low"]),
                         "close": float(bar["Close"]), "volume": float(bar["Volume"]),
                         "provider": "Yahoo Finance", "price_basis": "adjusted",
                         "retrieved_at": now})
    if bars:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO signal_intraday_bars
                (signal_id, ticker, bar_timestamp, open, high, low, close, volume,
                 provider, price_basis, retrieved_at)
                VALUES (:signal_id, :ticker, :bar_timestamp, :open, :high, :low, :close, :volume,
                        :provider, :price_basis, :retrieved_at)
                ON CONFLICT (signal_id, bar_timestamp) DO UPDATE SET
                high=excluded.high, low=excluded.low, close=excluded.close,
                volume=excluded.volume, retrieved_at=excluded.retrieved_at
            """), bars)
    return len(bars)


def refresh(batch: int = 200) -> dict:
    url = serving_url()
    if not url:
        print("  SUPABASE_DB_URL not set — skipping cloud intraday")
        return {}
    engine = create_engine(url)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    with engine.connect() as conn:
        max_date = conn.execute(
            text("SELECT MAX(date) FROM stock_prices")).scalar()
        cutoff = (date.fromisoformat(max_date) - timedelta(days=30)).isoformat()
        # dates are ISO text → lexicographic comparison is correct
        ref = pd.read_sql_query(
            text(
                """
                SELECT sp.ticker, sp.close AS prev_close, av.avg_vol, s.title
                FROM stock_prices sp
                JOIN (SELECT ticker, MAX(date) d FROM stock_prices
                      GROUP BY ticker) last
                     ON last.ticker = sp.ticker AND last.d = sp.date
                JOIN (SELECT ticker, AVG(volume) avg_vol FROM stock_prices
                      WHERE date > :cutoff GROUP BY ticker) av
                     ON av.ticker = sp.ticker
                LEFT JOIN stocks s ON s.ticker = sp.ticker
                """
            ),
            conn, params={"cutoff": cutoff}).set_index("ticker")
        history_cutoff = (date.fromisoformat(max_date) - timedelta(days=60)).isoformat()
        history = pd.read_sql_query(
            text("SELECT p.ticker, p.date, p.close, p.volume, s.title "
                 "FROM stock_prices p LEFT JOIN stocks s ON s.ticker=p.ticker "
                 "WHERE p.date >= :cutoff ORDER BY p.ticker, p.date"),
            conn, params={"cutoff": history_cutoff})

    tickers = ref.index.tolist()
    quotes = []
    for i in range(0, len(tickers), batch):
        chunk = [f"{t}.IS" for t in tickers[i:i + batch]]
        data = yf.download(chunk, period="1d", interval="1d",
                           group_by="ticker", auto_adjust=True,
                           progress=False, threads=True)
        for t in tickers[i:i + batch]:
            try:
                bar = data[f"{t}.IS"].dropna(how="all")
                if bar.empty:
                    continue
                quotes.append((t, float(bar["Open"].iloc[-1]), float(bar["Close"].iloc[-1]),
                               float(bar["Volume"].iloc[-1])))
            except KeyError:
                continue

    q = pd.DataFrame(quotes, columns=["ticker", "open", "price", "volume"]) \
        .set_index("ticker")
    live = q.join(ref, how="inner")
    live["chg_pct"] = (live["price"] / live["prev_close"] - 1) * 100
    live["turnover_mn"] = live["price"] * live["volume"] / 1e6
    live["vol_vs_20d"] = live["volume"] / live["avg_vol"]
    exhaustion_watch = build_watch(history, live)
    signal_rows = ledger_rows(exhaustion_watch, now)
    recorded_signals = _record_signal_observations(engine, signal_rows)
    captured_bars = _capture_signal_intraday_bars(engine, signal_rows, now)
    liquid = live[live["turnover_mn"] >= 10]

    breadth = {
        "ts": now,
        "advancers": int((live["chg_pct"] > 0.1).sum()),
        "decliners": int((live["chg_pct"] < -0.1).sum()),
        "turnover_bn_try": round(float(live["turnover_mn"].sum() / 1e3), 1),
    }

    def board(df, col, n=10, asc=False):
        d = df.sort_values(col, ascending=asc).head(n)
        return [{"ticker": t, "title": (r["title"] or "")[:40],
                 "price": round(r["price"], 2),
                 "chg_pct": round(r["chg_pct"], 2),
                 "turnover_mn": round(r["turnover_mn"], 0),
                 "vol_vs_20d": round(r["vol_vs_20d"], 1)}
                for t, r in d.iterrows()]

    movers = {"gainers": board(liquid, "chg_pct"),
              "losers": board(liquid, "chg_pct", asc=True),
              "turnover": board(liquid, "turnover_mn"),
              "unusual_volume": board(
                  liquid[liquid["vol_vs_20d"] > 2], "vol_vs_20d")}

    snap = {}
    idx = yf.download(["XU100.IS", "USDTRY=X", "GC=F"], period="2d",
                      interval="1d", group_by="ticker", progress=False,
                      auto_adjust=False)
    for label, sym in [("BIST100", "XU100.IS"), ("USD/TRY", "USDTRY=X"),
                       ("Gold (USD/oz)", "GC=F")]:
        try:
            closes = idx[sym]["Close"].dropna()
            snap[label] = {"level": round(float(closes.iloc[-1]), 2),
                           "chg_1d": round(float(
                               closes.iloc[-1] / closes.iloc[-2] - 1), 4)}
        except Exception:
            continue

    payload = json.dumps(
        _clean({"ts": now, "quotes": len(quotes), "breadth": breadth,
                "movers": movers, "snapshot": snap,
                "exhaustion_watch": {
                    "status": "experimental risk context; not investment advice or a trade signal",
                    "state": "active" if exhaustion_watch else "no qualifying events",
                    "provider": "Yahoo Finance",
                    "price_basis": "adjusted",
                    "gap_calculation_timestamp": now,
                    "source_note": "Yahoo adjusted daily-bar open, delayed/revisable; no auction queue, spread, or fill data.",
                    "candidates": exhaustion_watch,
                }}),
        ensure_ascii=False, allow_nan=False, default=str)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM system_status WHERE key = 'intraday'"))
        conn.execute(
            text("INSERT INTO system_status(key, value, updated_at) "
                 "VALUES ('intraday', :v, :t)"),
            {"v": payload, "t": datetime.utcnow().isoformat(
                timespec="seconds")})
    engine.dispose()
    return {"ts": now, "quotes": len(quotes), "recorded_signals": recorded_signals,
            "captured_intraday_bars": captured_bars,
            **breadth}


if __name__ == "__main__":
    # Direct entry point so the cloud cron can run
    #   python -m tefaslab.intraday_cloud
    # without importing tefaslab.cli, which eagerly pulls in the whole
    # package (kap/pdfplumber, report/tabulate, …) that this job doesn't
    # need. Keeps the CI install minimal and fast.
    print(refresh())
