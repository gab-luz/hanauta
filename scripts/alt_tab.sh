#!/usr/bin/env bash
set -euo pipefail

exec "$HOME/.config/i3/.venv/bin/python" \
  "$HOME/.config/i3/hanauta/src/pyqt/widget-window-switcher/window_switcher.py"
