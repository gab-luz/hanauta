#!/usr/bin/env bash

set -euo pipefail

THEME="${1:-}"
ICON_THEME="${2:-}"
COLOR_SCHEME="${3:-prefer-dark}"

if [ -z "$THEME" ]; then
  echo "Usage: $0 <theme-name> [icon-theme] [prefer-dark|prefer-light]"
  exit 1
fi

# Default icon theme to Material Design Papirus based on theme name
if [ -z "$ICON_THEME" ]; then
  case "$THEME" in
    *Dark|*dark*|*night*)
      ICON_THEME="Papirus-Dark"
      ;;
    *Light|*light*)
      ICON_THEME="Papirus-Light"
      ;;
    *)
      ICON_THEME="Papirus"
      ;;
  esac
fi

GTK3_PATH="$HOME/.themes/$THEME"
GTK3_CONFIG_PATH="$HOME/.config/gtk-3.0"
GTK4_PATH="$HOME/.config/gtk-4.0"
GTK2_RC_PATH="$HOME/.gtkrc-2.0"

if [ -d "$GTK3_PATH" ] || [ -d "$HOME/.local/share/themes/$THEME" ]; then
  unset GTK_THEME || true
  systemctl --user unset-environment GTK_THEME >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface gtk-theme "$THEME" || true
  gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME" || true
  gsettings set org.gnome.desktop.interface color-scheme "$COLOR_SCHEME" || true
fi

write_gtk_settings_ini() {
  local target_dir="$1"
  mkdir -p "$target_dir"
  {
    echo "[Settings]"
    echo "gtk-theme-name=$THEME"
    echo "gtk-icon-theme-name=$ICON_THEME"
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      echo "gtk-application-prefer-dark-theme=1"
    else
      echo "gtk-application-prefer-dark-theme=0"
    fi
  } > "$target_dir/settings.ini"
}

write_gtk_settings_ini "$GTK3_CONFIG_PATH"
write_gtk_settings_ini "$GTK4_PATH"

write_gtk2_settings() {
  {
    echo "gtk-theme-name=\"$THEME\""
    if [ -n "$ICON_THEME" ]; then
      echo "gtk-icon-theme-name=\"$ICON_THEME\""
    fi
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      echo "gtk-application-prefer-dark-theme=1"
    else
      echo "gtk-application-prefer-dark-theme=0"
    fi
  } > "$GTK2_RC_PATH"
}

write_gtk2_settings

# Apply Qt color scheme via qt5ct/qt6ct if available
QT_COLORS_DIR="$HOME/.themes/$THEME/qt"
if [ -d "$QT_COLORS_DIR" ]; then
  # qt5ct
  if [ -d "$HOME/.config/qt5ct/colors" ]; then
    cp "$QT_COLORS_DIR/colors.conf" "$HOME/.config/qt5ct/colors/$THEME.conf" 2>/dev/null || true
  fi
  # qt6ct
  if [ -d "$HOME/.config/qt6ct/colors" ]; then
    cp "$QT_COLORS_DIR/colors.conf" "$HOME/.config/qt6ct/colors/$THEME.conf" 2>/dev/null || true
  fi
  # Kvantum
  KVANTUM_THEME_DIR="$HOME/.themes/$THEME/Kvantum"
  if [ -d "$KVANTUM_THEME_DIR" ]; then
    KV_CONFIG="$HOME/.config/Kvantum/$THEME"
    mkdir -p "$KV_CONFIG"
    cp -a "$KVANTUM_THEME_DIR/." "$KV_CONFIG/" 2>/dev/null || true
  fi
fi

notify-send "Theme" "Applied theme: $THEME" >/dev/null 2>&1 || true
