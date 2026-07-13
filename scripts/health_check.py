"""One-shot system health check: local DB, Supabase, scheduled tasks."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tefaslab import db, health  # noqa: E402
from tefaslab.publish import serving_url  # noqa: E402

print("=== local SQLite health ===")
conn = db.connect()
code = health.report(conn)
conn.close()

print("\n=== Supabase connectivity + counts ===")
url = serving_url()
if not url:
    print("SUPABASE_DB_URL not found by publish.serving_url()")
else:
    from sqlalchemy import create_engine, text
    engine = create_engine(url)
    with engine.connect() as c:
        for t in ("funds", "prices", "stock_prices", "dash_quality"):
            n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:<15} {n:>10,} rows")
    engine.dispose()

print("\n=== Windows scheduled tasks ===")
for task in ("BIST-Daily-Pipeline", "BIST-Intraday"):
    r = subprocess.run(["schtasks", "/Query", "/TN", task, "/FO", "LIST"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        lines = [l for l in r.stdout.splitlines()
                if l.startswith(("TaskName", "Next Run Time", "Status"))]
        print(f"  {task}: " + " | ".join(lines))
    else:
        print(f"  {task}: NOT FOUND")
