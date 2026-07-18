"""Durable snapshot of the compute database + a data/code fingerprint.

The authoritative compute DB (data/funds.db) otherwise lives only in the
GitHub Actions cache — which can evict, taking the forward-only KAP
holdings history with it. This makes a clean, consistent single-file
copy (VACUUM INTO — folds the WAL, defragments) and a manifest that
records the DB sha256 (data hash) + git commit (code hash) + row counts
+ as-of date. The workflow compresses the copy and uploads both to a
GitHub Release, which is durable.

The manifest IS the reproducibility freeze: to cite a finding later,
reference the snapshot tag — it pins exactly which data and which code
produced it. Standalone (stdlib only) so it can never break from a
package import and needs no install.
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB = Path(os.environ.get("FUNDS_DB", "data/funds.db"))
OUT = Path("funds-snapshot.db")
MANIFEST = Path("snapshot_manifest.json")
TABLES = ["funds", "prices", "allocations", "stock_prices", "stocks",
          "benchmarks", "fund_holdings", "kap_disclosures"]
FLOORS = {"funds": 2000, "prices": 1_000_000, "stock_prices": 300_000}


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def git_sha() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    if not DB.exists():
        print(f"FAIL: {DB} not found — is the DB restored from cache?")
        return 1
    conn = sqlite3.connect(DB)
    check = conn.execute("PRAGMA quick_check").fetchone()[0]
    if check != "ok":
        print(f"FAIL: integrity check returned: {check}")
        return 1

    counts = {}
    for t in TABLES:
        try:
            counts[t] = conn.execute(
                f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[t] = None
    latest = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]

    if OUT.exists():
        OUT.unlink()
    conn.execute("VACUUM INTO ?", (OUT.as_posix(),))
    conn.close()

    # Verify the COPY we are about to ship — not just the source. A
    # partial VACUUM (disk full on the runner) leaves a truncated file
    # while the source still passes every check above.
    out = sqlite3.connect(OUT)
    try:
        out_check = out.execute("PRAGMA quick_check").fetchone()[0]
        out_funds = out.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
    finally:
        out.close()
    if out_check != "ok":
        print(f"FAIL: snapshot copy failed integrity: {out_check}")
        return 1
    if out_funds != counts.get("funds"):
        print(f"FAIL: snapshot copy is incomplete — funds {out_funds} "
              f"!= source {counts.get('funds')}")
        return 1

    manifest = {
        "created_utc": datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "db_sha256": sha256(OUT),
        "db_bytes": OUT.stat().st_size,
        "latest_price_date": latest,
        "row_counts": counts,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

    # never publish a truncated/empty snapshot as if it were good
    low = [f"{t}={counts.get(t)}(<{f})" for t, f in FLOORS.items()
           if (counts.get(t) or 0) < f]
    if low:
        print("FAIL: row counts below floor, refusing to snapshot: "
              + ", ".join(low))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
