#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/i3-startup.log

{
  SETTINGS_BIN="$HOME/.config/i3/hanauta/bin/hanauta-settings"
  SETTINGS_PY="$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py"
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/notification-daemon/notification_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-service" 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" >/tmp/hanauta-notification-daemon.log 2>&1 &
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-service" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-service" >/tmp/hanauta-service.log 2>&1 &
  fi
  if [ -x "$SETTINGS_BIN" ]; then
    "$SETTINGS_BIN" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
    "$SETTINGS_BIN" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
    "$SETTINGS_BIN" --restore-vpn >/tmp/hanauta-vpn-restore.log 2>&1 &
  else
    "$HOME/.config/i3/.venv/bin/python" "$SETTINGS_PY" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
    "$HOME/.config/i3/.venv/bin/python" "$SETTINGS_PY" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
    "$HOME/.config/i3/.venv/bin/python" "$SETTINGS_PY" --restore-vpn >/tmp/hanauta-vpn-restore.log 2>&1 &
  fi
} >>"$LOG" 2>&1
