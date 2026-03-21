#!/usr/bin/env bash

WALLPAPER="$1"
SETTINGS_FILE="$HOME/.local/state/hanauta/notification-center/settings.json"

if [ -z "$WALLPAPER" ]; then
  echo "Usage: $0 <wallpaper-path>"
  exit 1
fi

if [ ! -f "$WALLPAPER" ]; then
  echo "File not found: $WALLPAPER"
  exit 1
fi

feh --bg-fill "$WALLPAPER"
ln -sf "$WALLPAPER" "$HOME/.wallpapers/wallpaper.png" 2>/dev/null

should_notify=1

if [ "${HANAUTA_SUPPRESS_WALLPAPER_NOTIFY:-0}" = "1" ]; then
  should_notify=0
elif [ -f "$SETTINGS_FILE" ]; then
  notify_enabled="$(python3 - "$SETTINGS_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
enabled = False
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
appearance = payload.get("appearance", {}) if isinstance(payload, dict) else {}
if isinstance(appearance, dict):
    enabled = bool(appearance.get("wallpaper_change_notifications_enabled", False))
print("1" if enabled else "0")
PY
)"
  if [ "$notify_enabled" != "1" ]; then
    should_notify=0
  fi
fi

if [ "$should_notify" = "1" ]; then
  notify-send "Wallpaper" "Applied: $(basename "$WALLPAPER")"
fi
