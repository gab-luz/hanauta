#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"

if [ -x "$HOME/.config/i3/.venv/bin/python" ]; then
  exec "$HOME/.config/i3/.venv/bin/python" "$HOME/.config/i3/hanauta/src/pyqt/launcher/launcher.py"
fi

exec python3 "$HOME/.config/i3/hanauta/src/pyqt/launcher/launcher.py"
