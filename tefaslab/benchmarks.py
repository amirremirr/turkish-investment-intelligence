"""Benchmark series ingestion (Priority 1).

Free, keyless sources via Yahoo Finance: BIST indices, FX, gold.
Gram-gold TRY is derived: COMEX gold (USD/oz) x USDTRY / 31.1034768.

CPI and the CBRT policy rate need a (free) TCMB EVDS API key; the
schema already accommodates them as extra series (`cpi`, `policy_rate`)
once a key is available.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from . import db

GRAMS_PER_OZ = 31.1034768

TICKERS = {
    "bist100": "XU100.IS",
    "bist30": "XU030.IS",
    "usdtry": "USDTRY=X",
    "eurtry": "EURTRY=X",
    "gold_usd_oz": "GC=F",
    "nasdaq": "^IXIC",
    "sp500": "^GSPC",
    # BIST sector indices (only these two have Yahoo history; other
    # sector performance is computed from our own stock_prices)
    "sector_banks": "XBANK.IS",
    "sector_industrials": "XUSIN.IS",
}


def _closes(ticker: str, start: str) -> pd.Series:
    data = yf.download(ticker, start=start, progress=False,
                       auto_adjust=True)
    if data is None or data.empty:
        return pd.Series(dtype=float)
    close = data["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance MultiIndex columns
        close = close.iloc[:, 0]
    return close.dropna()


def fetch_benchmarks(start: str = "2024-01-01", db_path=db.DB_PATH) -> dict:
    """Download all benchmark series and upsert into SQLite."""
    conn = db.connect(db_path)
    counts = {}
    series_data: dict[str, pd.Series] = {}

    for name, ticker in TICKERS.items():
        s = _closes(ticker, start)
        series_data[name] = s
        rows = [(name, d.strftime("%Y-%m-%d"), float(v))
                for d, v in s.items() if np.isfinite(v)]
        db.upsert_benchmarks(conn, rows)
        counts[name] = len(rows)
        print(f"  {name:<12} {ticker:<10} {len(rows)} rows")

    # derived TRY series (aligned on common dates with USDTRY)
    fx = series_data.get("usdtry")
    derived = {
        "gold_try_gram": ("gold_usd_oz", 1 / GRAMS_PER_OZ),
        "nasdaq_try": ("nasdaq", 1.0),
    }
    if fx is not None and not fx.empty:
        for name, (source, scale) in derived.items():
            src = series_data.get(source)
            if src is None or src.empty:
                continue
            s = (src * scale * fx).dropna()
            rows = [(name, d.strftime("%Y-%m-%d"), float(v))
                    for d, v in s.items() if np.isfinite(v)]
            db.upsert_benchmarks(conn, rows)
            counts[name] = len(rows)
            print(f"  {name} (derived)   {len(rows)} rows")

    conn.commit()
    conn.close()
    return counts


def load_series(conn, series: str) -> pd.Series:
    df = pd.read_sql_query(
        "SELECT date, value FROM benchmarks WHERE series = ? ORDER BY date",
        conn, params=(series,), parse_dates=["date"])
    return df.set_index("date")["value"]
