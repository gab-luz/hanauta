#!/usr/bin/env bash
set -uo pipefail

LOG=/tmp/i3-startup.log
exec >>"$LOG" 2>&1
if [ -x "$HOME/.config/i3/.venv/bin/python" ]; then
  PYTHON_BIN="$HOME/.config/i3/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi
CURSOR_THEME_DEFAULT="sweet-cursors"
CURSOR_SIZE_DEFAULT="24"
HANAUTA_SCRIPTS_DIR="$HOME/.config/i3/hanauta/scripts"

resolve_plugin_script_path() {
  local plugin_hint="$1"
  local script_name="$2"
  PYTHONPATH="$HOME/.config/i3/hanauta/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - "$plugin_hint" "$script_name" <<'PY' || true
import sys
from pathlib import Path

from pyqt.shared.plugin_runtime import resolve_plugin_script

hint = str(sys.argv[1]).strip()
script = str(sys.argv[2]).strip()
resolved = resolve_plugin_script(script, [hint] if hint else None, required=False)
print(str(resolved) if resolved else "")
PY
  return 0
}

kill_script_if_running() {
  local script_path="$1"
  [ -n "$script_path" ] || return 0
  pkill -f "$script_path" 2>/dev/null || true
}

launch_python_script() {
  local script_path="$1"
  local log_path="$2"
  [ -n "$script_path" ] || return 0
  [ -f "$script_path" ] || return 0
  "$PYTHON_BIN" "$script_path" >"$log_path" 2>&1 &
}

warm_hanauta_service_caches() {
  local script_path="$1"
  local log_path="$2"
  if [ -f "$script_path" ]; then
    "$PYTHON_BIN" "$script_path" >"$log_path" 2>&1 &
  fi
}

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
REMINDER_DAEMON_SCRIPT="$(resolve_plugin_script_path reminders reminder_daemon.py)"
KDECONNECT_DAEMON_SCRIPT="$(resolve_plugin_script_path kdeconnect kdeconnect_battery_daemon.py)"
GAME_MODE_DAEMON_SCRIPT="$(resolve_plugin_script_path game-mode lutris_gamemode_daemon.py)"
VIRTUALIZATION_DAEMON_SCRIPT="$(resolve_plugin_script_path virtualization virtualization_daemon.py)"
CRYPTO_NOTIFIER_SCRIPT="$(resolve_plugin_script_path crypto crypto_notifier.py)"
UPDATES_NOTIFIER_SCRIPT="$(resolve_plugin_script_path updates updates_notifier.py)"
WALLPAPER_PROVIDER_SCRIPT="$(resolve_plugin_script_path wallpaper-manager wallpaper_provider_daemon.py)"
WALLPAPER_THUMBNAIL_SCRIPT="$(resolve_plugin_script_path wallpaper-manager wallpaper_thumbnail_service.py)"
HOME_ASSISTANT_PREFETCH_SCRIPT="$(resolve_plugin_script_path home-assistant home_assistant_icon_prefetch.py)"
LOCK_OSD_DAEMON_SCRIPT="$(resolve_plugin_script_path lock-osd lock_osd_daemon.py)"

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
  pkill -x picom 2>/dev/null || true
  picom --config "$HOME/.config/i3/picom.conf" --daemon >/tmp/picom.log 2>&1 || true
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
  kill_script_if_running "$REMINDER_DAEMON_SCRIPT"
  kill_script_if_running "$KDECONNECT_DAEMON_SCRIPT"
  kill_script_if_running "$GAME_MODE_DAEMON_SCRIPT"
  kill_script_if_running "$VIRTUALIZATION_DAEMON_SCRIPT"
  kill_script_if_running "$CRYPTO_NOTIFIER_SCRIPT"
  kill_script_if_running "$UPDATES_NOTIFIER_SCRIPT"
  kill_script_if_running "$WALLPAPER_PROVIDER_SCRIPT"
  kill_script_if_running "$WALLPAPER_THUMBNAIL_SCRIPT"
  kill_script_if_running "$HOME_ASSISTANT_PREFETCH_SCRIPT"
  kill_script_if_running "$LOCK_OSD_DAEMON_SCRIPT"
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
  warm_hanauta_service_caches \
    "$HANAUTA_SCRIPTS_DIR/cache_bar_services.py" \
    "/tmp/hanauta-cache-bar-services.log"
  warm_hanauta_service_caches \
    "$HANAUTA_SCRIPTS_DIR/cache_services_sections.py" \
    "/tmp/hanauta-cache-services-sections.log"
  launch_python_script "$REMINDER_DAEMON_SCRIPT" "/tmp/hanauta-reminder-daemon.log"
  launch_python_script "$KDECONNECT_DAEMON_SCRIPT" "/tmp/hanauta-kdeconnect-battery-daemon.log"
  launch_python_script "$GAME_MODE_DAEMON_SCRIPT" "/tmp/hanauta-lutris-gamemode-daemon.log"
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
    launch_python_script "$VIRTUALIZATION_DAEMON_SCRIPT" "/tmp/hanauta-virtualization-daemon.log"
  fi
  launch_python_script "$CRYPTO_NOTIFIER_SCRIPT" "/tmp/hanauta-crypto-notifier.log"
  launch_python_script "$UPDATES_NOTIFIER_SCRIPT" "/tmp/hanauta-updates-notifier.log"
  launch_python_script "$WALLPAPER_PROVIDER_SCRIPT" "/tmp/hanauta-wallpaper-provider.log"
  launch_python_script "$WALLPAPER_THUMBNAIL_SCRIPT" "/tmp/hanauta-wallpaper-thumbnails.log"
  launch_python_script "$HOME_ASSISTANT_PREFETCH_SCRIPT" "/tmp/hanauta-ha-icon-prefetch.log"
  launch_python_script "$LOCK_OSD_DAEMON_SCRIPT" "/tmp/hanauta-lock-osd.log"
  if [ -x "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" ]; then
    "$HOME/.config/i3/hanauta/bin/hanauta-wallcache" >/tmp/hanauta-wallcache.log 2>&1 &
  fi
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-displays >/tmp/hanauta-display-restore.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-wallpaper >/tmp/hanauta-wallpaper-restore.log 2>&1 &
  "$PYTHON_BIN" "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" --restore-vpn >/tmp/hanauta-vpn-restore.log 2>&1 &
  "$HOME/.config/i3/hanauta/scripts/open_dock.sh" >/tmp/hanauta-dock-launcher.log 2>&1 &
  "$HOME/.config/i3/hanauta/scripts/open_bar.sh" >/tmp/hanauta-bar-launcher.log 2>&1 &
} || true
