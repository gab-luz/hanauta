#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

SCRIPT_CANDIDATES=(
  "$HOME/.config/i3/hanauta/plugins/wallpaper_manager/wallpaper_manager.py"
  "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_manager.py"
  "$HOME/dev/hanauta-plugin-wallpaper-manager/wallpaper_manager.py"
)

for script in "${SCRIPT_CANDIDATES[@]}"; do
  if [ -f "$script" ]; then
    exec "$PYTHON_BIN" "$script"
  fi
done

echo "Hanauta Wallpaper Manager script was not found in known locations." >&2
exit 1
