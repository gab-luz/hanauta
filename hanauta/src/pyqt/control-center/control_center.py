#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))
ROOT = APP_DIR.parents[0]
CONTROL_CENTER_BINARY = ROOT / "bin" / "hanauta-control-center"
NOTIFICATION_CENTER = APP_DIR / "pyqt" / "notification-center" / "notification_center.py"

from pyqt.shared.runtime import entry_command


def main() -> int:
    args = sys.argv[1:]
    if CONTROL_CENTER_BINARY.exists():
        completed = subprocess.run([str(CONTROL_CENTER_BINARY), *args], check=False)
        return int(completed.returncode)
    completed = subprocess.run(entry_command(NOTIFICATION_CENTER, "--control-center", *args), check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
