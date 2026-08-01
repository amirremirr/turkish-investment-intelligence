"""Persist the small, stateful KAP/MKK recovery ledger independently.

GitHub Actions caches are immutable and are restored by prefix.  The general
``funds.db`` cache therefore cannot be trusted as the sole checkpoint for a
long-running, rate-limited MKK scan: an unrelated daily run may legitimately
have a newer cache key while holding an older scan cursor.

This utility exports only KAP/MKK tables to a compact SQLite sidecar and later
merges that checkpoint into a restored serving database.  The sidecar becomes
the authoritative recovery cursor; the main database remains the source for
all other daily analytics.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from tefaslab import kap


# These are intentionally complete snapshots, not deltas.  A monthly report
# replaces a fund/month snapshot, so retaining its related ledgers together is
# necessary to resume safely after an interrupted job.
STATE_TABLES = (
    "fund_holdings",
    "kap_disclosures",
    "kap_monthly_status",
    "fund_holdings_scope",
    "mkk_funds",
    "mkk_disclosures",
    "mkk_scan_state",
    "mkk_monthly_scan_state",
    "mkk_deferred_pages",
)

# The scan and deferral ledgers are only meaningful as a complete snapshot.
# Replacing them avoids mixing a newer cursor with stale deferred pages.
REPLACE_TABLES = {
    "mkk_scan_state",
    "mkk_monthly_scan_state",
    "mkk_deferred_pages",
}


def _quote(identifier: str) -> str:
    """Quote a fixed SQLite identifier defensively."""
    return '"' + identifier.replace('"', '""') + '"'


def _columns(conn: sqlite3.Connection, schema: str, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(
        f"PRAGMA {_quote(schema)}.table_info({_quote(table)})"
    )]


def _summary(conn: sqlite3.Connection) -> str:
    state = conn.execute(
        "SELECT period, head_index, cursor FROM mkk_monthly_scan_state "
        "ORDER BY period DESC LIMIT 1"
    ).fetchone()
    reports = conn.execute("SELECT COUNT(*) FROM mkk_disclosures").fetchone()[0]
    if not state:
        return f"MKK disclosures={reports}; no monthly cursor"
    period, head, cursor = state
    return (f"period={period}; cursor={cursor}; head={head}; "
            f"indexes advanced={max(0, int(head) - int(cursor))}; "
            f"MKK disclosures={reports}")


def export_state(database: Path, state_file: Path) -> None:
    """Write the recovery tables from ``database`` to ``state_file``."""
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        state_file.unlink()

    source = sqlite3.connect(database)
    destination = sqlite3.connect(state_file)
    try:
        kap._ensure_schema(source)
        for table in STATE_TABLES:
            row = source.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not row or not row[0]:
                continue
            destination.execute(str(row[0]))
            cols = _columns(source, "main", table)
            quoted = ", ".join(_quote(col) for col in cols)
            rows = source.execute(
                f"SELECT {quoted} FROM main.{_quote(table)}"
            ).fetchall()
            if rows:
                placeholders = ", ".join("?" for _ in cols)
                destination.executemany(
                    f"INSERT INTO {_quote(table)} ({quoted}) VALUES ({placeholders})",
                    rows,
                )
        destination.commit()
        print(f"KAP recovery checkpoint exported: {_summary(source)}")
    finally:
        destination.close()
        source.close()


def import_state(database: Path, state_file: Path) -> None:
    """Merge a recovery checkpoint into ``database`` without touching analytics."""
    if not state_file.is_file():
        print("No KAP recovery checkpoint to restore.")
        return

    # The checkpoint is small (ledgers and monthly snapshots, not the complete
    # analytics database). Keep it as a normal second connection rather than
    # using SQLite ATTACH: attached-schema queries have differed between the
    # Windows and hosted-runner SQLite builds.
    checkpoint = sqlite3.connect(state_file)
    try:
        checkpoint_tables = {
            str(row[0]) for row in checkpoint.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        destination = sqlite3.connect(database)
        try:
            kap._ensure_schema(destination)
            destination.execute("BEGIN")
            for table in STATE_TABLES:
                if table not in checkpoint_tables:
                    continue
                source_columns = set(_columns(checkpoint, "main", table))
                columns = [column for column in _columns(destination, "main", table)
                           if column in source_columns]
                if not columns:
                    continue
                quoted = ", ".join(_quote(column) for column in columns)
                if table in REPLACE_TABLES:
                    destination.execute(f"DELETE FROM main.{_quote(table)}")
                rows = checkpoint.execute(
                    f"SELECT {quoted} FROM main.{_quote(table)}"
                ).fetchall()
                if rows:
                    placeholders = ", ".join("?" for _ in columns)
                    destination.executemany(
                        f"INSERT OR REPLACE INTO main.{_quote(table)} ({quoted}) "
                        f"VALUES ({placeholders})", rows
                    )
            destination.commit()
            print(f"KAP recovery checkpoint restored: {_summary(destination)}")
        finally:
            destination.close()
    finally:
        checkpoint.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("--database", type=Path, default=Path("data/funds.db"))
    parser.add_argument("--state", type=Path, default=Path("data/kap-recovery-state.db"))
    args = parser.parse_args()
    if args.action == "export":
        export_state(args.database, args.state)
    else:
        import_state(args.database, args.state)


if __name__ == "__main__":
    main()
