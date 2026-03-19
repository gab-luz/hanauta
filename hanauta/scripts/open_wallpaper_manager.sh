#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

exec "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_manager.py"
