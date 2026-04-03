#!/usr/bin/env bash

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"
LAUNCH_LOG="/tmp/hanauta-dock-launcher.log"
exec >>"$LAUNCH_LOG" 2>&1
set -x

{
  printf '[%s] open_dock start\n' "$(date '+%F %T')"
  printf 'DISPLAY=%s\n' "${DISPLAY:-}"
  printf 'XAUTHORITY=%s\n' "${XAUTHORITY:-}"
}

pkill -x hanauta-dock 2>/dev/null || true
pkill -f "$HOME/.config/i3/hanauta/src/pyqt/dock/dock.py" 2>/dev/null || true

PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
printf 'python=%s\n' "$PYTHON_BIN"

nohup "$PYTHON_BIN" \
  "$HOME/.config/i3/hanauta/src/pyqt/dock/dock.py" \
  >/tmp/hanauta-dock.log 2>&1 </dev/null &
child_pid="$!"
printf 'spawned_pid=%s\n' "$child_pid" >>"$LAUNCH_LOG"
sleep 0.4
if kill -0 "$child_pid" 2>/dev/null; then
  printf 'status=running\n' >>"$LAUNCH_LOG"
else
  printf 'status=exited\n' >>"$LAUNCH_LOG"
fi

exit 0
