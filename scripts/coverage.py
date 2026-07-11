"""Quick DB coverage report."""
import sqlite3

conn = sqlite3.connect("data/funds.db")

print("price rows by month:")
q = ("SELECT substr(date,1,7) m, COUNT(*), COUNT(DISTINCT code) "
     "FROM prices GROUP BY m ORDER BY m")
for m, rows, funds in conn.execute(q):
    print(f"  {m}: {rows:>7,} rows  {funds:>5} funds")

print("\nallocation rows by month:")
q = ("SELECT substr(date,1,7) m, COUNT(*) FROM allocations "
     "GROUP BY m ORDER BY m")
for m, rows in conn.execute(q):
    print(f"  {m}: {rows:>8,} rows")
