#!/usr/bin/env bash

state_file="/tmp/eww-caffeine.enabled"
pid_file="/tmp/eww-caffeine.pid"

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Caffeine" "$1"
  fi
}

start_inhibit() {
  systemd-inhibit --what=idle:sleep:handle-lid-switch \
    --who="eww" --why="Caffeine toggle from eww bar" \
    --mode=block sleep infinity &
  echo $! > "$pid_file"
}

stop_inhibit() {
  if [ -f "$pid_file" ]; then
    kill "$(cat "$pid_file")" 2>/dev/null
    rm -f "$pid_file"
  fi
}

case "$1" in
  toggle)
    if [ -f "$state_file" ]; then
      rm -f "$state_file"
      stop_inhibit
      notify "Caffeine desativado"
    else
      touch "$state_file"
      start_inhibit
      notify "Caffeine ativado"
    fi
    ;;
  status)
    if [ -f "$state_file" ]; then
      echo "on"
    else
      echo "off"
    fi
    ;;
  icon)
    if [ -f "$state_file" ]; then
      echo ""
    else
      echo ""
    fi
    ;;
  *)
    exit 0
    ;;
esac
