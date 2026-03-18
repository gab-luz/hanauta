from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import fcntl


STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
QUEUE_FILE = STATE_DIR / "reminders_queue.json"
LOCK_FILE = STATE_DIR / "reminders_queue.lock"
DAEMON_PID_FILE = STATE_DIR / "reminder-daemon.pid"
DAEMON_STATUS_FILE = STATE_DIR / "reminder-daemon.json"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def queue_lock() -> Iterator[None]:
    ensure_state_dir()
    with LOCK_FILE.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_queue() -> list[dict]:
    ensure_state_dir()
    try:
        payload = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def save_queue(entries: list[dict]) -> None:
    ensure_state_dir()
    temp_path = QUEUE_FILE.with_suffix(".tmp")
    temp_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    temp_path.replace(QUEUE_FILE)


def enqueue_reminder(title: str, body: str, severity: str, delay_seconds: int = 0) -> dict:
    due_at = datetime.now() + timedelta(seconds=max(0, int(delay_seconds)))
    entry = {
        "id": str(uuid4()),
        "title": str(title or "Reminder"),
        "body": str(body or "Time is up."),
        "severity": str(severity or "discrete"),
        "created_at": _now_iso(),
        "due_at": due_at.isoformat(timespec="seconds"),
    }
    with queue_lock():
        queue = load_queue()
        queue.append(entry)
        queue.sort(key=lambda item: str(item.get("due_at", "")))
        save_queue(queue)
    return entry


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def daemon_is_running() -> bool:
    try:
        pid = int(DAEMON_PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    return _pid_is_running(pid)


def ensure_daemon_running(command: list[str]) -> bool:
    if daemon_is_running() or not command:
        return daemon_is_running() or bool(command)
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
