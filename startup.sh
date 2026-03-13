#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/i3-startup.log

{
  pkill -x eww 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/notification-daemon/notification_daemon.py" 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/eww/scripts/notifications-cache-daemon.sh" 2>/dev/null || true
  "$HOME/.config/i3/.venv/bin/python" "$HOME/.config/i3/hanauta/src/pyqt/notification-daemon/notification_daemon.py" >/tmp/hanauta-notification-daemon.log 2>&1 &
  "$HOME/.config/i3/hanauta/src/eww/scripts/notifications-cache-daemon.sh" >/tmp/eww-notifications-cache.log 2>&1 &
  "$HOME/.config/i3/.venv/bin/python" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
  "$HOME/.config/i3/.venv/bin/python" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
} >>"$LOG" 2>&1
