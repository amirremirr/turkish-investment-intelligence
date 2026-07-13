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

    tickers = ref.index.tolist()
    quotes = []
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
                quotes.append((t, float(bar["Close"].iloc[-1]),
                               float(bar["Volume"].iloc[-1])))
            except KeyError:
                continue

    q = pd.DataFrame(quotes, columns=["ticker", "price", "volume"]) \
        .set_index("ticker")
    live = q.join(ref, how="inner")
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
                "movers": movers, "snapshot": snap}),
        ensure_ascii=False, allow_nan=False, default=str)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM system_status WHERE key = 'intraday'"))
        conn.execute(
            text("INSERT INTO system_status(key, value, updated_at) "
                 "VALUES ('intraday', :v, :t)"),
            {"v": payload, "t": datetime.utcnow().isoformat(
                timespec="seconds")})
    engine.dispose()
    return {"ts": now, "quotes": len(quotes), **breadth}


if __name__ == "__main__":
    # Direct entry point so the cloud cron can run
    #   python -m tefaslab.intraday_cloud
    # without importing tefaslab.cli, which eagerly pulls in the whole
    # package (kap/pdfplumber, report/tabulate, …) that this job doesn't
    # need. Keeps the CI install minimal and fast.
    print(refresh())
