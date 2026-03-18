#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))

from pyqt.shared.runtime import entry_command
from reminder_queue import (
    DAEMON_PID_FILE,
    DAEMON_STATUS_FILE,
    load_queue,
    queue_lock,
    save_queue,
)


REMINDER_ALERT_SCRIPT = HERE / "reminder_alert.py"
POLL_INTERVAL_SECONDS = 1.0


def _parse_due_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _write_status(state: str, details: str) -> None:
    DAEMON_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "service": "hanauta-reminder-daemon",
        "status": state,
        "details": details,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "queue_file": str((DAEMON_STATUS_FILE.parent / "reminders_queue.json").name),
    }
    DAEMON_STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _spawn_alert(entry: dict) -> bool:
    command = entry_command(
        REMINDER_ALERT_SCRIPT,
        "--title",
        str(entry.get("title", "Reminder")),
        "--body",
        str(entry.get("body", "Time is up.")),
        "--severity",
        str(entry.get("severity", "discrete")),
    )
    if not command:
        return False
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def _process_queue() -> tuple[int, int]:
    now = datetime.now()
    triggered = 0
    kept: list[dict] = []
    with queue_lock():
        queue = load_queue()
        for entry in queue:
            due_at = _parse_due_at(str(entry.get("due_at", "")))
            if due_at is None:
                continue
            if due_at <= now:
                if _spawn_alert(entry):
                    triggered += 1
                    continue
            kept.append(entry)
        if len(kept) != len(queue):
            save_queue(kept)
    return triggered, len(kept)


def _cleanup(*_args: object) -> None:
    try:
        if DAEMON_PID_FILE.exists():
            DAEMON_PID_FILE.unlink()
    except Exception:
        pass
    _write_status("stopped", "Reminder daemon stopped.")
    raise SystemExit(0)


def main() -> int:
    DAEMON_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        if DAEMON_PID_FILE.exists():
            existing = int(DAEMON_PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(existing, 0)
            return 0
    except Exception:
        pass

    DAEMON_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    _write_status("running", "Reminder daemon is watching the queue.")

    while True:
        triggered, pending = _process_queue()
        if triggered:
            _write_status("running", f"Triggered {triggered} reminder(s). {pending} pending.")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
