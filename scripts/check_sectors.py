import sqlite3

from tefaslab import db, stockintel

conn = db.connect()
rows = conn.execute(
    "SELECT COALESCE(sector,'(null)') s, COUNT(*) FROM stocks "
    "WHERE ticker IN (SELECT DISTINCT ticker FROM stock_prices) "
    "GROUP BY s ORDER BY 2 DESC").fetchall()
for s, n in rows:
    print(f"  {s:<25} {n}")

print("\nsector performance:")
print(stockintel.sector_performance(conn).round(4).to_string())
conn.close()
