"""Regression coverage for the durable monthly KAP checkpoint."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from tefaslab import kap


def _state_script():
    path = Path(__file__).parents[1] / "scripts" / "kap_recovery_state.py"
    spec = importlib.util.spec_from_file_location("kap_recovery_state", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checkpoint_restores_newer_mkk_cursor_and_disclosures(tmp_path):
    tool = _state_script()
    source_path = tmp_path / "recovered.db"
    checkpoint_path = tmp_path / "kap-recovery-state.db"
    stale_path = tmp_path / "stale.db"

    source = sqlite3.connect(source_path)
    kap._ensure_schema(source)
    source.execute(
        "INSERT INTO mkk_monthly_scan_state "
        "(period, cursor, head_index, live_cursor, exhausted, updated_at) "
        "VALUES ('2026-06', 1208468, 1231017, 1231018, 0, '2026-08-01T00:00:00')"
    )
    source.execute(
        "INSERT INTO mkk_disclosures "
        "(disclosure_index, fund_code, status, checked_at) "
        "VALUES (1209000, 'FPH', 'indexed', '2026-08-01T00:00:00')"
    )
    source.commit()
    source.close()
    tool.export_state(source_path, checkpoint_path)

    stale = sqlite3.connect(stale_path)
    kap._ensure_schema(stale)
    stale.execute(
        "INSERT INTO mkk_monthly_scan_state "
        "(period, cursor, head_index, live_cursor, exhausted, updated_at) "
        "VALUES ('2026-06', 1228468, 1231017, 1231018, 0, '2026-07-28T00:00:00')"
    )
    stale.commit()
    stale.close()

    tool.import_state(stale_path, checkpoint_path)
    restored = sqlite3.connect(stale_path)
    assert restored.execute(
        "SELECT cursor FROM mkk_monthly_scan_state WHERE period='2026-06'"
    ).fetchone() == (1208468,)
    assert restored.execute(
        "SELECT fund_code FROM mkk_disclosures WHERE disclosure_index=1209000"
    ).fetchone() == ("FPH",)
    restored.close()
