#!/usr/bin/env bash

set -euo pipefail

THEME="${1:-}"
ICON_THEME="${2:-}"
COLOR_SCHEME="${3:-prefer-dark}"

if [ -z "$THEME" ]; then
  echo "Usage: $0 <theme-name> [icon-theme] [prefer-dark|prefer-light]"
  exit 1
fi

GTK3_PATH="$HOME/.themes/$THEME"
GTK4_PATH="$HOME/.config/gtk-4.0"

if [ -d "$GTK3_PATH" ] || [ -d "$HOME/.local/share/themes/$THEME" ]; then
  gsettings set org.gnome.desktop.interface gtk-theme "$THEME" || true
  if [ -n "$ICON_THEME" ]; then
    gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME" || true
  fi
  gsettings set org.gnome.desktop.interface color-scheme "$COLOR_SCHEME" || true
fi

mkdir -p "$GTK4_PATH"
if [ -f "$GTK4_PATH/settings.ini" ]; then
  sed -i "s/^gtk-theme-name=.*/gtk-theme-name=$THEME/" "$GTK4_PATH/settings.ini" || true
  if grep -q '^gtk-application-prefer-dark-theme=' "$GTK4_PATH/settings.ini"; then
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      sed -i 's/^gtk-application-prefer-dark-theme=.*/gtk-application-prefer-dark-theme=1/' "$GTK4_PATH/settings.ini"
    else
      sed -i 's/^gtk-application-prefer-dark-theme=.*/gtk-application-prefer-dark-theme=0/' "$GTK4_PATH/settings.ini"
    fi
  else
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      echo "gtk-application-prefer-dark-theme=1" >> "$GTK4_PATH/settings.ini"
    else
      echo "gtk-application-prefer-dark-theme=0" >> "$GTK4_PATH/settings.ini"
    fi
  fi
else
  {
    echo "[Settings]"
    echo "gtk-theme-name=$THEME"
    if [ "$COLOR_SCHEME" = "prefer-dark" ]; then
      echo "gtk-application-prefer-dark-theme=1"
    else
      echo "gtk-application-prefer-dark-theme=0"
    fi
  } > "$GTK4_PATH/settings.ini"
fi

notify-send "Theme" "Applied theme: $THEME"
