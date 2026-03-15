#!/bin/sh

STATE_FILE="/tmp/hanauta-cava-overlay.state"
ALACRITTY_CONFIG="$HOME/.config/i3/hanauta/scripts/alacritty-cava.toml"
CAVA_CONFIG="$HOME/.config/i3/hanauta/scripts/cava.conf"
CLASS="CavaOverlay"

is_running() {
  pgrep -af "alacritty.*$CLASS" >/dev/null 2>&1
}

screen_width() {
  xrandr --current 2>/dev/null | awk '/\*/ { split($1, a, "x"); print a[1]; exit }'
}

open_overlay() {
  if is_running; then
    return
  fi

  width=300
  height=38
  screen_w="$(screen_width)"
  [ -n "$screen_w" ] || screen_w=1920
  x=$(( (screen_w - width) / 2 ))
  y=9

  alacritty --class "$CLASS","$CLASS" --config-file "$ALACRITTY_CONFIG" -e cava -p "$CAVA_CONFIG" >/tmp/cava-overlay.log 2>&1 &

  (
    sleep 0.5
    i3-msg "[class=\"$CLASS\"] floating enable, sticky enable, border pixel 0, resize set $width $height, move position $x $y" >/dev/null 2>&1
  ) &
}

close_overlay() {
  pkill -f "alacritty.*$CLASS" >/dev/null 2>&1
}

sync_overlay() {
  status="$("$HOME/.config/i3/hanauta/scripts/mpris.sh" status 2>/dev/null)"
  if [ "$status" = "Playing" ]; then
    open_overlay
    printf '%s\n' "running"
  else
    close_overlay
    printf '%s\n' "stopped"
  fi
}

case "${1:-sync}" in
  open)
    open_overlay
    ;;
  close)
    close_overlay
    ;;
  sync)
    sync_overlay
    ;;
  *)
    printf '%s\n' "usage: $0 {open|close|sync}" >&2
    exit 1
    ;;
esac
