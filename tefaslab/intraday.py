"""Intraday refresh (15-minute cadence) for the stock-market layer.

Fetches delayed quotes (Yahoo, ~15 min) for all BIST tickers plus
index/FX/gold, and rebuilds the LIVE views: market snapshot, breadth,
movers. Provisional data stays in its own table (`live_quotes`) and in
`system_status['intraday']` — the clean daily tables are never touched,
so nightly analytics remain based on official closes only.

Fund data (TEFAS) is deliberately absent: NAVs publish once per day.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd
import yfinance as yf

from . import db
from .pipeline import _status

SNAPSHOT_TICKERS = {"BIST100": "XU100.IS", "USD/TRY": "USDTRY=X",
                    "Gram gold (TRY)": None,  # derived below
                    "Gold (USD/oz)": "GC=F"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS live_quotes (
    ticker      TEXT PRIMARY KEY,
    ts          TEXT NOT NULL,
    price       REAL,
    volume      REAL
);
"""


def refresh(db_path=db.DB_PATH, batch: int = 200) -> dict:
    conn = db.connect(db_path)
    conn.executescript(SCHEMA)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    tickers = [t for (t,) in conn.execute(
        "SELECT DISTINCT ticker FROM stock_prices")]
    rows = []
    for i in range(0, len(tickers), batch):
        chunk = [f"{t}.IS" for t in tickers[i:i + batch]]
        data = yf.download(chunk, period="1d", interval="1d",
                           group_by="ticker", auto_adjust=False,
                           progress=False, threads=True)
        for t in tickers[i:i + batch]:
            try:
                bar = data[f"{t}.IS"].dropna(how="all")
                if bar.empty:
                    continue
                rows.append((t, now, float(bar["Close"].iloc[-1]),
                             float(bar["Volume"].iloc[-1])))
            except KeyError:
                continue
    conn.executemany("INSERT OR REPLACE INTO live_quotes VALUES (?,?,?,?)",
                     rows)
    conn.commit()

    # previous official closes + 20d avg volume for context
    ref = pd.read_sql_query(
        """
        SELECT sp.ticker, sp.close AS prev_close, av.avg_vol, s.title
        FROM stock_prices sp
        JOIN (SELECT ticker, MAX(date) d FROM stock_prices GROUP BY ticker)
             last ON last.ticker = sp.ticker AND last.d = sp.date
        JOIN (SELECT ticker, AVG(volume) avg_vol FROM stock_prices
              WHERE date > date((SELECT MAX(date) FROM stock_prices),
                                '-30 days') GROUP BY ticker) av
             ON av.ticker = sp.ticker
        LEFT JOIN stocks s ON s.ticker = sp.ticker
        """, conn).set_index("ticker")
    live = pd.read_sql_query("SELECT * FROM live_quotes", conn) \
        .set_index("ticker").join(ref, how="inner")
    live["chg_pct"] = (live["price"] / live["prev_close"] - 1) * 100
    live["turnover_mn"] = live["price"] * live["volume"] / 1e6
    live["vol_vs_20d"] = live["volume"] / live["avg_vol"]
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

    # index/FX snapshot from single quotes
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

    _status(conn, "intraday", {"ts": now, "quotes": len(rows),
                               "breadth": breadth, "movers": movers,
                               "snapshot": snap})
    conn.close()
    return {"ts": now, "quotes": len(rows), **breadth}
