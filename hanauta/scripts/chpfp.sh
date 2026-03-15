#!/usr/bin/env bash

FILE=$(zenity --file-selection --title="Choose Profile Picture" --file-filter="Images | *.png *.jpg *.jpeg *.gif *.bmp" 2>/dev/null)

if [ -n "$FILE" ] && [ -f "$FILE" ]; then
  cp "$FILE" "$HOME/.face.png"
  cp "$FILE" "$HOME/.face.jpg"
  sleep 0.5
  eww -c ~/.config/i3/hanauta/src/eww update refresh_pfp=$(date +%s)
  notify-send -i "$HOME/.face.png" "Profile Picture" "Profile picture updated!"
else
  exit 1
fi
