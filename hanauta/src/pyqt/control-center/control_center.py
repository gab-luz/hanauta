#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[0]
CONTROL_CENTER_BINARY = ROOT / "bin" / "hanauta-control-center"
NOTIFICATION_CENTER = APP_DIR / "pyqt" / "notification-center" / "notification_center.py"
VENV_PYTHON = ROOT.parent / ".venv" / "bin" / "python"


def main() -> int:
    args = sys.argv[1:]
    if CONTROL_CENTER_BINARY.exists():
        completed = subprocess.run([str(CONTROL_CENTER_BINARY), *args], check=False)
        return int(completed.returncode)
    python_bin = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    completed = subprocess.run([python_bin, str(NOTIFICATION_CENTER), "--control-center", *args], check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
