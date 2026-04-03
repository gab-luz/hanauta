#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/i3-startup.log
PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
CURSOR_THEME_DEFAULT="sweet-cursors"
CURSOR_SIZE_DEFAULT="24"

read_gtk_setting() {
  local key="$1"
  local file="$HOME/.config/gtk-3.0/settings.ini"
  [ -f "$file" ] || return 1
  awk -F= -v k="$key" '
    {
      gsub(/^[ \t]+|[ \t]+$/, "", $1)
    }
    $1 == k {
      gsub(/^[ \t]+|[ \t]+$/, "", $2)
      print $2
      exit
    }
  ' "$file"
}

read_gtk2_setting() {
  local key="$1"
  local file="$HOME/.gtkrc-2.0"
  [ -f "$file" ] || return 1
  awk -F= -v k="$key" '
    {
      gsub(/^[ \t]+|[ \t]+$/, "", $1)
    }
    $1 == k {
      gsub(/^[ \t"]+|[ \t"]+$/, "", $2)
      print $2
      exit
    }
  ' "$file"
}

resolve_cursor_theme() {
  local value=""
  value="$(read_gtk_setting "gtk-cursor-theme-name" 2>/dev/null || true)"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
    return 0
  fi

  value="$(read_gtk2_setting "gtk-cursor-theme-name" 2>/dev/null || true)"
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
    return 0
  fi

  if [ -f "$HOME/.icons/default/index.theme" ]; then
    value="$(awk -F= '$1=="Inherits"{print $2; exit}' "$HOME/.icons/default/index.theme" 2>/dev/null || true)"
    if [ -n "$value" ]; then
      printf '%s\n' "$value"
      return 0
    fi
  fi

  value="$(gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null | tr -d "'" || true)"
  if [ -n "$value" ] && [ "$value" != "''" ]; then
    printf '%s\n' "$value"
    return 0
  fi

  printf '%s\n' "$CURSOR_THEME_DEFAULT"
}

resolve_cursor_size() {
  local value=""
  value="$(read_gtk_setting "gtk-cursor-theme-size" 2>/dev/null || true)"
  if [ -n "$value" ] && [ "$value" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$value"
    return 0
  fi

  value="$(read_gtk2_setting "gtk-cursor-theme-size" 2>/dev/null || true)"
  if [ -n "$value" ] && [ "$value" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$value"
    return 0
  fi

  value="$(gsettings get org.gnome.desktop.interface cursor-size 2>/dev/null | tr -d "'" || true)"
  if [ -n "$value" ] && [ "$value" -gt 0 ] 2>/dev/null; then
    printf '%s\n' "$value"
    return 0
  fi

  printf '%s\n' "$CURSOR_SIZE_DEFAULT"
}

write_icons_default_theme() {
  local theme="$1"
  local icons_default_dir="$HOME/.icons/default"
  mkdir -p "$icons_default_dir"
  cat > "$icons_default_dir/index.theme" <<EOF
[Icon Theme]
Inherits=$theme
EOF
}

CURSOR_THEME="$(resolve_cursor_theme)"
CURSOR_SIZE="$(resolve_cursor_size)"

{
  export XCURSOR_THEME="$CURSOR_THEME"
  export XCURSOR_SIZE="$CURSOR_SIZE"
  write_icons_default_theme "$CURSOR_THEME"
  xrdb -merge <<EOF 2>/dev/null || true
Xcursor.theme: $CURSOR_THEME
Xcursor.size: $CURSOR_SIZE
EOF
  gsettings set org.gnome.desktop.interface cursor-theme "$CURSOR_THEME" 2>/dev/null || true
  gsettings set org.gnome.desktop.interface cursor-size "$CURSOR_SIZE" 2>/dev/null || true
  systemctl --user set-environment XCURSOR_THEME="$CURSOR_THEME" XCURSOR_SIZE="$CURSOR_SIZE" 2>/dev/null || true
  dbus-update-activation-environment --systemd XCURSOR_THEME="$CURSOR_THEME" XCURSOR_SIZE="$CURSOR_SIZE" 2>/dev/null || true
  unset GTK_THEME
  systemctl --user unset-environment GTK_THEME 2>/dev/null || true
  dbus-update-activation-environment --systemd GTK_THEME= 2>/dev/null || true
  if command -v setxkbmap >/dev/null 2>&1; then
    keyboard_layout="$("$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

settings_path = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
value = "us"
try:
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
if isinstance(payload, dict):
    input_settings = payload.get("input", {})
    if isinstance(input_settings, dict):
        candidate = str(input_settings.get("keyboard_layout", "")).strip()
        if candidate:
            value = " ".join(part for part in candidate.split() if part)
print(value)
PY
)"
    if [ -n "$keyboard_layout" ]; then
      layout_name="${keyboard_layout%% *}"
      layout_variant=""
      if [ "$layout_name" != "$keyboard_layout" ]; then
        layout_variant="${keyboard_layout#* }"
      fi
      if [ -n "$layout_variant" ]; then
        setxkbmap "$layout_name" -variant "$layout_variant" >/dev/null 2>&1 || true
      else
        setxkbmap "$layout_name" >/dev/null 2>&1 || true
      fi
    fi
  fi
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/notification-daemon/notification_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-service" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-reminders/reminder_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-kdeconnect/kdeconnect_battery_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-game-mode/lutris_gamemode_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-virtualization/virtualization_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-crypto/crypto_notifier.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-updates/updates_notifier.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_provider_daemon.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-wallpaper-manager/wallpaper_thumbnail_service.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/src/pyqt/widget-home-assistant/home_assistant_icon_prefetch.py" 2>/dev/null || true
  pkill -f "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" 2>/dev/null || true
  pkill -x volnoti 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  if command -v volnoti >/dev/null 2>&1; then
    volnoti >/tmp/volnoti.log 2>&1 &
  fi
  "$HOME/.config/i3/hanauta/bin/hanauta-notifyd" >/tmp/hanauta-notification-daemon.log 2>&1 &
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-service" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-service" >/tmp/hanauta-service.log 2>&1 &
  fi
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-reminders/reminder_daemon.py" >/tmp/hanauta-reminder-daemon.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-kdeconnect/kdeconnect_battery_daemon.py" >/tmp/hanauta-kdeconnect-battery-daemon.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-game-mode/lutris_gamemode_daemon.py" >/tmp/hanauta-lutris-gamemode-daemon.log 2>&1 &
  if "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

settings_path = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
try:
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
services = payload.get("services", {}) if isinstance(payload, dict) else {}
virtualization = services.get("virtualization", {}) if isinstance(services, dict) else {}
enabled = bool(virtualization.get("enabled", False)) if isinstance(virtualization, dict) else False
raise SystemExit(0 if enabled else 1)
PY
  then
    "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/widget-virtualization/virtualization_daemon.py" >/tmp/hanauta-virtualization-daemon.log 2>&1 &
  fi
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
