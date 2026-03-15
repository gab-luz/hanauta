#!/usr/bin/env bash

THEME="$1"

if [ -z "$THEME" ]; then
  echo "Usage: $0 <theme-name>"
  exit 1
fi

GTK3_PATH="$HOME/.themes/$THEME"
GTK4_PATH="$HOME/.config/gtk-4.0"

if [ -d "$GTK3_PATH" ]; then
  gsettings set org.gnome.desktop.interface gtk-theme "$THEME"
  gsettings set org.gnome.desktop.interface icon-theme "$THEME"
  gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
  
  if [ -f "$GTK3_PATH/index.theme" ]; then
    sed -i "s/^GtkTheme=.*/GtkTheme=$THEME/" "$GTK3_PATH/index.theme" 2>/dev/null
  fi
fi

if [ -d "$GTK4_PATH" ]; then
  if [ -f "$GTK4_PATH/settings.ini" ]; then
    sed -i "s/^gtk-theme-name=.*/gtk-theme-name=$THEME/" "$GTK4_PATH/settings.ini"
  else
    echo "[Settings]" > "$GTK4_PATH/settings.ini"
    echo "gtk-theme-name=$THEME" >> "$GTK4_PATH/settings.ini"
  fi
fi

if command -v matugen &> /dev/null; then
  matugen theme "$THEME" 2>/dev/null || true
fi

notify-send "Theme" "Applied theme: $THEME"
