#!/usr/bin/env bash

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"
LAUNCH_LOG="/tmp/hanauta-bar-launcher.log"
exec >>"$LAUNCH_LOG" 2>&1
set -x

{
  printf '[%s] open_bar start\n' "$(date '+%F %T')"
  printf 'DISPLAY=%s\n' "${DISPLAY:-}"
  printf 'XAUTHORITY=%s\n' "${XAUTHORITY:-}"
}

pkill -x hanauta-bar 2>/dev/null || true
pkill -x hanauta-game-mode-popup 2>/dev/null || true
pkill -x hanauta-ai-popup 2>/dev/null || true
pkill -f "$HOME/.config/i3/hanauta/src/pyqt/bar/ui_bar.py" 2>/dev/null || true

PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
printf 'python=%s\n' "$PYTHON_BIN"
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  printf 'status=failed reason=python-not-found\n' >>"$LAUNCH_LOG"
  exit 1
fi

nohup "$PYTHON_BIN" \
  "$HOME/.config/i3/hanauta/src/pyqt/bar/ui_bar.py" \
  --ui "$HOME/.config/i3/hanauta/src/pyqt/bar/bar.ui" \
  >/tmp/hanauta-ui-bar.log 2>&1 </dev/null &
child_pid="$!"
printf 'spawned_pid=%s\n' "$child_pid" >>"$LAUNCH_LOG"
sleep 0.4
if kill -0 "$child_pid" 2>/dev/null; then
  printf 'status=running\n' >>"$LAUNCH_LOG"
else
  printf 'status=exited\n' >>"$LAUNCH_LOG"
fi

exit 0
