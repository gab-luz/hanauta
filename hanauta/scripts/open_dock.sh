#!/usr/bin/env bash

export PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}"
DOCK_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/hanauta-dock"
mkdir -p "$DOCK_CACHE_DIR" 2>/dev/null || true
LAUNCH_LOG="/tmp/hanauta-dock-launcher.log"
exec >>"$LAUNCH_LOG" 2>&1
set -x

{
  printf '[%s] open_dock start\n' "$(date '+%F %T')"
  printf 'DISPLAY=%s\n' "${DISPLAY:-}"
  printf 'XAUTHORITY=%s\n' "${XAUTHORITY:-}"
  printf 'XDG_CACHE_HOME=%s\n' "${XDG_CACHE_HOME:-}"
}

pkill -x hanauta-dock 2>/dev/null || true
pkill -f "$HOME/.config/i3/hanauta/src/pyqt/dock/dock.py" 2>/dev/null || true

PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
printf 'python=%s\n' "$PYTHON_BIN"
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  printf 'status=failed reason=python-not-found\n' >>"$LAUNCH_LOG"
  exit 1
fi

if [ -n "${XAUTHORITY:-}" ] && [ ! -f "$XAUTHORITY" ]; then
  fallback_auth="$HOME/.Xauthority"
  if [ -f "$fallback_auth" ]; then
    export XAUTHORITY="$fallback_auth"
    printf 'xauthority_fallback=%s\n' "$XAUTHORITY" >>"$LAUNCH_LOG"
  fi
fi

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
  if [ -s /tmp/hanauta-dock.log ]; then
    printf 'last_log_tail<<EOF\n' >>"$LAUNCH_LOG"
    tail -n 80 /tmp/hanauta-dock.log >>"$LAUNCH_LOG" || true
    printf 'EOF\n' >>"$LAUNCH_LOG"
  fi
fi

exit 0
