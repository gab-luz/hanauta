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
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-kdeconnect/kdeconnect_battery_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-game-mode/lutris_gamemode_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-crypto/crypto_notifier.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-updates/updates_notifier.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_provider_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_thumbnail_service.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-home-assistant/home_assistant_icon_prefetch.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" >/tmp/hanauta-notification-daemon.log 2>&1 &
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-service" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-service" >/tmp/hanauta-service.log 2>&1 &
  fi
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-reminders/reminder_daemon.py" >/tmp/hanauta-reminder-daemon.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-kdeconnect/kdeconnect_battery_daemon.py" >/tmp/hanauta-kdeconnect-battery-daemon.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-game-mode/lutris_gamemode_daemon.py" >/tmp/hanauta-lutris-gamemode-daemon.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-crypto/crypto_notifier.py" >/tmp/hanauta-crypto-notifier.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-updates/updates_notifier.py" >/tmp/hanauta-updates-notifier.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_provider_daemon.py" >/tmp/hanauta-wallpaper-provider.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_thumbnail_service.py" >/tmp/hanauta-wallpaper-thumbnails.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-home-assistant/home_assistant_icon_prefetch.py" >/tmp/hanauta-ha-icon-prefetch.log 2>&1 &
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" >/tmp/hanauta-wallcache.log 2>&1 &
  fi
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-vpn >/tmp/hanauta-vpn-restore.log 2>&1 &
} >>"$LOG" 2>&1
