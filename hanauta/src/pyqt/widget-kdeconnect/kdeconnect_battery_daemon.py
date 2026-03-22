#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))

from pyqt.shared.runtime import entry_command
from reminder_queue import ensure_daemon_running, enqueue_reminder


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
PID_FILE = STATE_DIR / "kdeconnect-battery-daemon.pid"
STATUS_FILE = STATE_DIR / "kdeconnect-battery-daemon.json"
ALERT_STATE_FILE = STATE_DIR / "kdeconnect-battery-alert-state.json"
PHONE_INFO_SCRIPT = ROOT / "hanauta" / "scripts" / "phone_info.sh"
REMINDER_DAEMON = ROOT / "hanauta" / "src" / "pyqt" / "widget-reminders" / "reminder_daemon.py"
POLL_INTERVAL_SECONDS = 30


def _load_settings() -> dict:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _service_settings() -> dict:
    settings = _load_settings()
    services = settings.get("services", {})
    service = services.get("kdeconnect", {}) if isinstance(services, dict) else {}
    if not isinstance(service, dict):
        service = {}
    return {
        "enabled": bool(service.get("enabled", True)),
        "low_battery_fullscreen_notification": bool(service.get("low_battery_fullscreen_notification", False)),
        "low_battery_threshold": max(1, min(100, int(service.get("low_battery_threshold", 20) or 20))),
    }


def _load_alert_state() -> dict:
    try:
        payload = json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_alert_state(payload: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_status(status: str, details: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(
            {
                "service": "hanauta-kdeconnect-battery-daemon",
                "status": status,
                "details": details,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _phone_payload() -> dict:
    try:
        raw = subprocess.check_output([str(PHONE_INFO_SCRIPT)], text=True, stderr=subprocess.DEVNULL, timeout=8.0)
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _cleanup(*_args: object) -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass
    _write_status("stopped", "KDE Connect battery daemon stopped.")
    raise SystemExit(0)


def _battery_value(payload: dict) -> int | None:
    try:
        return int(str(payload.get("battery", "")).strip())
    except Exception:
        return None


def _should_reset_alert(state: dict, device_id: str, battery: int, threshold: int, status: str) -> bool:
    if not state:
        return True
    if state.get("device_id") != device_id:
        return True
    if str(status).strip().lower() == "charging":
        return True
    return battery > threshold + 3


def _trigger_low_battery_alert(name: str, battery: int, threshold: int) -> None:
    ensure_daemon_running(entry_command(REMINDER_DAEMON))
    enqueue_reminder(
        "Phone Battery Low",
        f"{name} is at {battery}% battery. Threshold: {threshold}%.",
        "disturbing",
        delay_seconds=0,
    )


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if PID_FILE.exists():
            existing = int(PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(existing, 0)
            return 0
    except Exception:
        pass

    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    _write_status("running", "Watching KDE Connect battery level.")

    while True:
        service = _service_settings()
        payload = _phone_payload()
        device_id = str(payload.get("id", "")).strip()
        name = str(payload.get("name", "Phone")).strip() or "Phone"
        status = str(payload.get("status", "")).strip()
        threshold = int(service.get("low_battery_threshold", 20))
        battery = _battery_value(payload)
        state = _load_alert_state()

        if not service.get("enabled", True) or not service.get("low_battery_fullscreen_notification", False):
            if state:
                _save_alert_state({})
            _write_status("running", "Low-battery fullscreen alerts are disabled.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if not device_id or battery is None:
            _write_status("running", "No reachable KDE Connect phone or battery unavailable.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if _should_reset_alert(state, device_id, battery, threshold, status):
            if state:
                _save_alert_state({})
            state = {}

        if str(status).strip().lower() != "charging" and battery <= threshold and not state:
            _trigger_low_battery_alert(name, battery, threshold)
            _save_alert_state(
                {
                    "device_id": device_id,
                    "battery": battery,
                    "threshold": threshold,
                    "alerted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
            _write_status("running", f"Triggered low-battery alert for {name} at {battery}%.")
        else:
            _write_status("running", f"{name} battery is {battery}% ({status or 'unknown'}).")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
