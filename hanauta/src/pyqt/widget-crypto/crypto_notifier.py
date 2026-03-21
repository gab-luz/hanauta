#!/usr/bin/env python3
from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.crypto import build_price_alerts, load_settings_state, load_tracker_state, save_tracker_state
from pyqt.shared.runtime import entry_command


ACTION_NOTIFICATION_SCRIPT = APP_DIR / "pyqt" / "shared" / "action_notification.py"
RUNNING = True


def _handle_exit(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False


def send_notification(summary: str, body: str, open_url: str, replace_id: int) -> None:
    if not ACTION_NOTIFICATION_SCRIPT.exists() or not open_url.strip():
        return
    command = entry_command(
        ACTION_NOTIFICATION_SCRIPT,
        "--app-name",
        "Hanauta Crypto",
        "--summary",
        summary,
        "--body",
        body,
        "--action-label",
        "Open",
        "--open-url",
        open_url,
        "--replace-id",
        str(replace_id),
    )
    if not command:
        return
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_exit)
    signal.signal(signal.SIGINT, _handle_exit)

    while RUNNING:
        settings = load_settings_state()
        state = load_tracker_state()
        try:
            alerts, next_state = build_price_alerts(settings, state)
        except Exception:
            alerts, next_state = [], state
        for alert in alerts:
            send_notification(
                str(alert.get("summary", "Crypto alert")),
                str(alert.get("body", "")),
                str(alert.get("url", "")),
                int(alert.get("replace_id", 0) or 0),
            )
        if next_state != state:
            save_tracker_state(next_state)
        for _ in range(60):
            if not RUNNING:
                break
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
