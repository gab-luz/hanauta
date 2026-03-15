#!/usr/bin/env bash

WALLPAPER="$1"

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

notify-send "Wallpaper" "Applied: $(basename $WALLPAPER)"
