#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
HANAUTA_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$HANAUTA_ROOT/.." && pwd)"
SRC_ROOT="$HANAUTA_ROOT/src"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

if [ -z "$PYTHON_BIN" ]; then
  notify-send -a "Hanauta Mail" "Hanauta Mail unavailable" "python3 was not found." >/dev/null 2>&1 || true
  exit 1
fi

PYTHONPATH="$SRC_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$@" <<'PY'
from __future__ import annotations

import subprocess
import sys

from pyqt.shared.plugin_runtime import resolve_plugin_script
from pyqt.shared.runtime import entry_command


def notify_unavailable(message: str) -> None:
    try:
        subprocess.Popen(
            ["notify-send", "-a", "Hanauta Mail", "Hanauta Mail unavailable", message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


mail_app = resolve_plugin_script("email_client.py", ["email-client", "mail"])
command = entry_command(mail_app, *sys.argv[1:]) if mail_app else []
if not command:
    notify_unavailable("Install the Hanauta email-client plugin first, then try again.")
    raise SystemExit(1)

try:
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
except Exception as exc:
    notify_unavailable(str(exc) or "Unable to launch the email-client plugin.")
    raise SystemExit(1)
PY
