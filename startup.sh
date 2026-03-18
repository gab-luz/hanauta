#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/i3-startup.log
PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

{
  unset GTK_THEME
  systemctl --user unset-environment GTK_THEME 2>/dev/null || true
  dbus-update-activation-environment --systemd GTK_THEME= 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/notification-daemon/notification_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-service" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-reminders/reminder_daemon.py" 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" >/tmp/hanauta-notification-daemon.log 2>&1 &
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-service" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-service" >/tmp/hanauta-service.log 2>&1 &
  fi
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-reminders/reminder_daemon.py" >/tmp/hanauta-reminder-daemon.log 2>&1 &
  "$HOME/.config/i3/hanauta/bin/hanauta-settings" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
  "$HOME/.config/i3/hanauta/bin/hanauta-settings" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
  "$HOME/.config/i3/hanauta/bin/hanauta-settings" --restore-vpn >/tmp/hanauta-vpn-restore.log 2>&1 &
} >>"$LOG" 2>&1
