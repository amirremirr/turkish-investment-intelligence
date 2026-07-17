"""Cloud health monitor — checks the whole serving chain in Supabase.

Standalone by design: imports only sqlalchemy + stdlib (no tefaslab, so
it can't break from a package-import issue, and needs a tiny CI install).
Reads SUPABASE_DB_URL from the environment.

Exits non-zero if any HARD check fails, so the monitoring workflow can
alert. Prints a readable report either way.
"""

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text


def _db_url() -> str | None:
    if os.environ.get("SUPABASE_DB_URL"):
        return os.environ["SUPABASE_DB_URL"]
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("SUPABASE_DB_URL="):
                return line.split("=", 1)[1].strip()
    return None

OK, WARN, FAIL = "ok", "warn", "FAIL"
results: list[tuple[str, str, str]] = []


def add(status, check, detail=""):
    results.append((status, check, detail))


def days_since_iso(d: str) -> int:
    return (date.today() - date.fromisoformat(d[:10])).days


def main() -> int:
    url = _db_url()
    if not url:
        print("SUPABASE_DB_URL not set")
        return 2
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 20})
        conn = engine.connect()
    except Exception as e:
        print(f"FAIL  cannot connect to Supabase: {e}")
        return 1

    def scalar(q):
        return conn.execute(text(q)).scalar()

    def status_row(key):
        return conn.execute(
            text("SELECT value, updated_at FROM system_status "
                 "WHERE key = :k"), {"k": key}).fetchone()

    # 1. connectivity
    add(OK, "supabase connection", url.split("@")[-1])

    # 2. pipeline-failure flag — but only "active" if no successful run
    #    has completed since (else it's a resolved past failure, not a
    #    reason to keep alerting). updated_at is ISO, so string compare.
    import json
    pf = status_row("pipeline_failed")
    pc = status_row("pipeline_complete")
    failed = False
    if pf and pf[0]:
        try:
            failed = bool(json.loads(pf[0]))
        except Exception:
            failed = pf[0] not in ("false", "null", "", None)
    superseded = bool(failed and pf and pf[1] and pc and pc[1]
                      and pc[1] >= pf[1])
    if failed and not superseded:
        add(FAIL, "pipeline flag",
            f"last pipeline run reported FAILURE: {str(pf[0])[:120]}")
    elif failed and superseded:
        add(OK, "pipeline flag",
            "a past failure was superseded by a later successful run")
    else:
        add(OK, "pipeline flag", "no active failure flag")

    # 3. fund price freshness (timezone-robust: uses data dates)
    pmax = scalar("SELECT MAX(date) FROM prices")
    if pmax is None:
        add(FAIL, "fund prices", "prices table empty")
    else:
        age = days_since_iso(pmax)
        add(FAIL if age > 6 else WARN if age > 4 else OK,
            "fund price freshness", f"latest {pmax} ({age}d old)")

    # 4. row-count sanity (detect truncation / partial publish)
    counts = {
        "funds": scalar("SELECT COUNT(*) FROM funds"),
        "prices": scalar("SELECT COUNT(*) FROM prices"),
        "stock_prices": scalar("SELECT COUNT(*) FROM stock_prices"),
        "dash_metrics": scalar("SELECT COUNT(*) FROM dash_metrics"),
        "dash_quality": scalar("SELECT COUNT(*) FROM dash_quality"),
    }
    floors = {"funds": 2000, "prices": 1_000_000, "stock_prices": 300_000,
              "dash_metrics": 1500, "dash_quality": 500}
    low = [f"{t}={n:,}(<{floors[t]:,})" for t, n in counts.items()
           if n is None or n < floors[t]]
    add(FAIL if low else OK, "row counts",
        "; ".join(low) if low else
        " · ".join(f"{t} {n:,}" for t, n in counts.items()))

    # 5. presentation tables present & non-empty
    dash = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name LIKE 'dash\\_%' ESCAPE '\\'")).fetchall()
    add(OK if len(dash) >= 8 else FAIL, "presentation tables",
        f"{len(dash)} dash_* tables present")

    # 6. nightly recency via system_status (loose window absorbs any TZ skew)
    pc = status_row("pipeline_complete")
    if pc and pc[1]:
        try:
            ts = datetime.fromisoformat(pc[1])
            age_h = (datetime.now() - ts).total_seconds() / 3600
            add(WARN if age_h > 40 else OK, "pipeline recency",
                f"last completion {pc[1]} (~{age_h:.0f}h ago)")
        except ValueError:
            add(WARN, "pipeline recency", f"unparseable ts {pc[1]}")
    else:
        add(WARN, "pipeline recency", "no pipeline_complete status")

    # 7. benchmark freshness
    bmax = scalar("SELECT MAX(date) FROM benchmarks")
    if bmax:
        add(WARN if days_since_iso(bmax) > 7 else OK,
            "benchmark freshness", f"latest {bmax}")

    # 8. intraday (informational — UTC ts; market-hours make staleness
    #    normal off-hours, so never a hard fail here)
    intra = status_row("intraday")
    if intra:
        import json
        try:
            tsi = json.loads(intra[0]).get("ts")
            age = (datetime.now(timezone.utc)
                   - datetime.strptime(tsi + " +0000", "%Y-%m-%d %H:%M %z")
                   ).total_seconds() / 60
            add(OK, "intraday", f"last {tsi} UTC ({age:.0f}m ago)")
        except Exception:
            add(WARN, "intraday", "present but unparseable")
    else:
        add(WARN, "intraday", "no intraday row yet")

    conn.close()
    engine.dispose()

    # report
    icons = {OK: "✓", WARN: "⚠", FAIL: "✗"}
    width = max(len(c) for _, c, _ in results)
    print(f"System health — {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    for status, check, detail in results:
        print(f" {icons[status]} {check:<{width}}  {detail}")
    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n{len(results)} checks: "
          f"{len(results) - fails - warns} ok, {warns} warn, {fails} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
