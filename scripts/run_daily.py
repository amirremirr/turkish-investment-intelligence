"""Scheduled entry point for the nightly pipeline.

Adds the operational layer around `tefaslab daily`:
  - logs to logs/daily_YYYY-MM-DD.log
  - retries once after 10 minutes if the run raises (TEFAS hiccups)
  - records pipeline_failed / pipeline_ok in system_status so the
    dashboard can surface staleness
  - best-effort Windows toast on final failure

Registered in Task Scheduler (weekdays 18:30) via scripts/run_daily.cmd.
Manual test:  python scripts/run_daily.py --skip-raw --no-retry
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tefaslab import db, pipeline  # noqa: E402

LOG_DIR = ROOT / "logs"
RETRY_WAIT_S = 600


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def notify_failure(message: str) -> None:
    """Best-effort Windows toast; never raises."""
    try:
        import subprocess
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;"
            "$t=[Windows.UI.Notifications.ToastNotificationManager]::"
            "GetTemplateContent([Windows.UI.Notifications."
            "ToastTemplateType]::ToastText02);"
            "$t.GetElementsByTagName('text').Item(0).AppendChild("
            "$t.CreateTextNode('BIST pipeline FAILED'))|Out-Null;"
            "$t.GetElementsByTagName('text').Item(1).AppendChild("
            f"$t.CreateTextNode('{message[:120]}'))|Out-Null;"
            "$n=[Windows.UI.Notifications.ToastNotification]::new($t);"
            "[Windows.UI.Notifications.ToastNotificationManager]::"
            "CreateToastNotifier('BIST Pipeline').Show($n)")
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       timeout=30, capture_output=True)
    except Exception:
        pass


def mark(key: str, value) -> None:
    conn = db.connect()
    pipeline._status(conn, key, value)
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-raw", action="store_true")
    parser.add_argument("--no-retry", action="store_true")
    args = parser.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"daily_{date.today()}.log"
    log = open(log_path, "a", encoding="utf-8")
    sys.stdout = sys.stderr = Tee(sys.__stdout__, log)
    print(f"\n===== pipeline start {datetime.now():%Y-%m-%d %H:%M:%S} =====")

    attempts = 1 if args.no_retry else 2
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            health_code = pipeline.run(skip_raw=args.skip_raw)
            mark("pipeline_failed", False)
            mark("pipeline_ok", {"health_exit": health_code,
                                 "attempt": attempt})
            print(f"===== pipeline OK (health exit {health_code}) =====")
            return 0
        except Exception as err:
            last_error = err
            print(f"attempt {attempt} FAILED: {err}")
            traceback.print_exc()
            if attempt < attempts:
                print(f"retrying in {RETRY_WAIT_S // 60} minutes...")
                time.sleep(RETRY_WAIT_S)

    mark("pipeline_failed", {"error": str(last_error)[:300]})
    notify_failure(str(last_error))
    print("===== pipeline FAILED after retries =====")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
