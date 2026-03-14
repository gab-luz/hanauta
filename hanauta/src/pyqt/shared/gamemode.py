from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "game-mode"
STATE_FILE = STATE_DIR / "state.json"
SERVICE_NAME = "gamemoded.service"


def _run_text(cmd: list[str], timeout: float = 4.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return 1, str(exc)


def gamemoded_available() -> bool:
    return shutil.which("gamemoded") is not None


def systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def service_enabled() -> bool:
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    services = payload.get("services", {})
    if not isinstance(services, dict):
        return False
    current = services.get("game_mode", {})
    if not isinstance(current, dict):
        return False
    return bool(current.get("enabled", False))


def is_active() -> bool:
    if systemctl_available():
        code, _ = _run_text(["systemctl", "--user", "is-active", SERVICE_NAME], timeout=2.0)
        if code == 0:
            return True
    code, _ = _run_text(["pgrep", "-x", "gamemoded"], timeout=2.0)
    return code == 0


def _persist_runtime(active: bool, note: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "active": bool(active),
                "note": note,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def summary() -> dict[str, object]:
    available = gamemoded_available()
    active = is_active() if available else False
    if not available:
        note = "Install the gamemode package to control gamemoded."
    elif active:
        note = "gamemoded is active for this session."
    else:
        note = "gamemoded is installed but currently inactive."
    return {
        "available": available,
        "active": active,
        "enabled": service_enabled(),
        "note": note,
    }


def set_active(enabled: bool) -> tuple[bool, str]:
    if not gamemoded_available():
        message = "gamemoded is not installed. Install gamemode first."
        _persist_runtime(False, message)
        return False, message

    if not systemctl_available():
        message = "systemctl --user is unavailable, so Hanauta cannot manage gamemoded yet."
        _persist_runtime(False, message)
        return False, message

    action = "start" if enabled else "stop"
    code, output = _run_text(["systemctl", "--user", action, SERVICE_NAME], timeout=6.0)
    if code != 0:
        message = output or f"Failed to {action} {SERVICE_NAME}."
        _persist_runtime(is_active(), message)
        return False, message

    active = is_active()
    message = "Game Mode enabled." if active else "Game Mode disabled."
    _persist_runtime(active, message)
    return True, message


def toggle_active() -> tuple[bool, str]:
    return set_active(not is_active())
