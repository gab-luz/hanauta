from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from pyqt.shared.runtime import entry_command, source_root
from pyqt.shared.plugin_runtime import resolve_plugin_script


CORE_FULLSCREEN_ALERT_SCRIPT = source_root() / "pyqt" / "shared" / "fullscreen_alert.py"
REMINDER_ALERT_SCRIPT = CORE_FULLSCREEN_ALERT_SCRIPT
if not REMINDER_ALERT_SCRIPT.exists():
    REMINDER_ALERT_SCRIPT = resolve_plugin_script("reminder_alert.py", ["reminders"]) or Path()


def _normalize_command(command: Sequence[str]) -> list[str]:
    return [str(part) for part in command if str(part).strip()]


def polkit_available() -> bool:
    return shutil.which("pkexec") is not None


def build_polkit_command(command: Sequence[str]) -> list[str]:
    normalized = _normalize_command(command)
    if not normalized:
        return []
    if normalized[0] == "pkexec":
        return normalized
    return ["pkexec", *normalized]


def run_with_polkit(
    command: Sequence[str],
    *,
    detached: bool = True,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> bool:
    wrapped = build_polkit_command(command)
    if not wrapped or not polkit_available():
        return False
    merged_env = dict(os.environ)
    if env:
        merged_env.update({str(key): str(value) for key, value in env.items()})
    try:
        if detached:
            subprocess.Popen(
                wrapped,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=merged_env,
            )
            return True
        result = subprocess.run(
            wrapped,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=merged_env,
        )
        return result.returncode == 0
    except Exception:
        return False


def fullscreen_alert_command(
    title: str,
    body: str,
    severity: str = "discrete",
    source_app: Optional[str] = None,
    source_icon: Optional[str] = None,
    source_topic: Optional[str] = None,
) -> list[str]:
    script_path = Path(REMINDER_ALERT_SCRIPT)
    if not script_path.exists():
        return []
    cmd = entry_command(
        script_path,
        "--title",
        str(title or "Plugin alert"),
        "--body",
        str(body or ""),
        "--severity",
        str(severity or "discrete"),
    )
    if source_app:
        cmd.extend(["--source-app", str(source_app)])
    if source_icon:
        cmd.extend(["--source-icon", str(source_icon)])
    if source_topic:
        cmd.extend(["--source-topic", str(source_topic)])
    return cmd


def trigger_fullscreen_alert(
    title: str,
    body: str,
    severity: str = "discrete",
    source_app: Optional[str] = None,
    source_icon: Optional[str] = None,
    source_topic: Optional[str] = None,
) -> bool:
    command = fullscreen_alert_command(title, body, severity, source_app, source_icon, source_topic)
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
