from __future__ import annotations

import subprocess
import shutil
from pathlib import Path


def _run_text(cmd: list[str], *, timeout: float = 2.5) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def hanauta_mail_desktop_installed(
    desktop_local_path: Path, desktop_system_path: Path
) -> bool:
    return desktop_local_path.exists() or desktop_system_path.exists()


def current_mailto_handler() -> str:
    if shutil.which("xdg-mime") is None:
        return ""
    return _run_text(["xdg-mime", "query", "default", "x-scheme-handler/mailto"]).strip()


def current_favorite_mail_handler() -> str:
    if shutil.which("xdg-settings") is None:
        return ""
    return _run_text(
        ["xdg-settings", "get", "default-url-scheme-handler", "mailto"]
    ).strip()

