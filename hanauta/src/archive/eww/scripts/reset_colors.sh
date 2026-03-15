#!/usr/bin/env bash

BAR_SCSS="$HOME/.config/i3/hanauta/src/eww/bar/bar.scss"
ACTIONS_SCSS="$HOME/.config/i3/hanauta/src/eww/actions/actions.scss"

if [ -f "$BAR_SCSS.orig" ]; then
  cp "$BAR_SCSS.orig" "$BAR_SCSS"
fi

if [ -f "$ACTIONS_SCSS.orig" ]; then
  cp "$ACTIONS_SCSS.orig" "$ACTIONS_SCSS"
fi

sassc -t expanded "$HOME/.config/i3/hanauta/src/eww/eww.scss.src" /tmp/eww.css && \
  sed '1{/^@charset/d;}' /tmp/eww.css > "$HOME/.config/i3/hanauta/src/eww/eww.css"

eww -c "$HOME/.config/i3/hanauta/src/eww" daemon --restart 2>/dev/null

notify-send "Matugen" "Reset to default colors"
