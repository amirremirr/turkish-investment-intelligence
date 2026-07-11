import sqlite3

conn = sqlite3.connect("data/funds.db")
n = conn.execute("SELECT COUNT(DISTINCT ticker) FROM stock_prices").fetchone()[0]
rows = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]
rng = conn.execute("SELECT MIN(date), MAX(date) FROM stock_prices").fetchone()
thyao = conn.execute(
    "SELECT date, close, volume FROM stock_prices "
    "WHERE ticker='THYAO' ORDER BY date DESC LIMIT 1").fetchone()
print(f"{n} tickers, {rows:,} rows, {rng[0]} .. {rng[1]}")
print("THYAO latest:", thyao)
