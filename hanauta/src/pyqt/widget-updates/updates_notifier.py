#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "updates-notifier"
STATE_FILE = STATE_DIR / "state.json"
CHECK_INTERVAL_SECONDS = 4 * 60 * 60
RUNNING = True

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.updates import build_notification, collect_update_payload, send_update_notification, updates_signature


def _handle_exit(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False


def load_state() -> dict:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("last_signature", "")
    payload.setdefault("last_checked_at", "")
    payload.setdefault("last_notified_at", "")
    return payload


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def perform_check() -> None:
    state = load_state()
    payload = collect_update_payload()
    signature = updates_signature(payload)
    total = len(payload.get("system_updates", [])) + len(payload.get("flatpak_updates", []))
    now = datetime.now().isoformat(timespec="seconds")

    state["last_checked_at"] = now
    if total <= 0:
        state["last_signature"] = ""
        save_state(state)
        return

    if signature != str(state.get("last_signature", "")):
        summary, body = build_notification(payload)
        if send_update_notification(summary, body):
            state["last_signature"] = signature
            state["last_notified_at"] = now
    save_state(state)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_exit)
    signal.signal(signal.SIGINT, _handle_exit)

    while RUNNING:
        try:
            perform_check()
        except Exception:
            pass
        for _ in range(CHECK_INTERVAL_SECONDS):
            if not RUNNING:
                break
            time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
