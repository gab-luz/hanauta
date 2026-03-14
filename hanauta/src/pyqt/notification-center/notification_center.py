#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher for the native Hanauta notification center with a legacy fallback.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[0]
NATIVE_BINARY = ROOT / "bin" / "hanauta-notification-center"
LEGACY_SCRIPT = APP_DIR / "pyqt" / "notification-center" / "notification_center_legacy.py"
VENV_PYTHON = ROOT.parent / ".venv" / "bin" / "python"


def main() -> int:
    args = sys.argv[1:]
    force_legacy = "--legacy" in args
    python_bin = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    if not force_legacy and NATIVE_BINARY.exists():
        completed = subprocess.run([str(NATIVE_BINARY), *args], check=False)
        return int(completed.returncode)
    if LEGACY_SCRIPT.exists():
        completed = subprocess.run([python_bin, str(LEGACY_SCRIPT), *args], check=False)
        return int(completed.returncode)
    print("No notification center implementation is available.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
