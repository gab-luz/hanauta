#!/usr/bin/env bash

set -euo pipefail

COLOR_SCHEME="${1:-}"

if [ "$COLOR_SCHEME" != "prefer-dark" ] && [ "$COLOR_SCHEME" != "prefer-light" ]; then
  echo "Usage: $0 <prefer-dark|prefer-light>" >&2
  exit 1
fi

GTK3_CONFIG_PATH="$HOME/.config/gtk-3.0"
GTK4_CONFIG_PATH="$HOME/.config/gtk-4.0"
GTK2_RC_PATH="$HOME/.gtkrc-2.0"

read_theme_from_gsettings() {
  local value=""
  value="$(gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null || true)"
  value="${value#\'}"
  value="${value%\'}"
  echo "$value"
}

read_theme_from_ini() {
  local ini_path="$1/settings.ini"
  if [ ! -f "$ini_path" ]; then
    return 0
  fi
  awk -F= '/^gtk-theme-name=/{print $2; exit 0}' "$ini_path" 2>/dev/null || true
}

THEME="$(read_theme_from_gsettings)"
if [ -z "$THEME" ]; then
  THEME="$(read_theme_from_ini "$GTK3_CONFIG_PATH")"
fi
if [ -z "$THEME" ]; then
  THEME="$(read_theme_from_ini "$GTK4_CONFIG_PATH")"
fi
if [ -z "$THEME" ]; then
  THEME="Adwaita"
fi

unset GTK_THEME || true
systemctl --user unset-environment GTK_THEME >/dev/null 2>&1 || true

gsettings set org.gnome.desktop.interface color-scheme "$COLOR_SCHEME" >/dev/null 2>&1 || true

write_gtk_settings_ini() {
  local target_dir="$1"
  mkdir -p "$target_dir"
  {
    echo "[Settings]"
    echo "gtk-theme-name=$THEME"
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      echo "gtk-application-prefer-dark-theme=1"
    else
      echo "gtk-application-prefer-dark-theme=0"
    fi
  } > "$target_dir/settings.ini"
}

write_gtk_settings_ini "$GTK3_CONFIG_PATH"
write_gtk_settings_ini "$GTK4_CONFIG_PATH"

{
  echo "gtk-theme-name=\"$THEME\""
  if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
    echo "gtk-application-prefer-dark-theme=1"
  else
    echo "gtk-application-prefer-dark-theme=0"
  fi
} > "$GTK2_RC_PATH"
