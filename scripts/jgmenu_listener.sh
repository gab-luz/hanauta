#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/i3/jgmenu"

exec >>/tmp/jgmenu_listener.log 2>&1
echo "[start] $(date -Is) pid=$$"

exec 9>/tmp/jgmenu_listener.lock
if ! flock -n 9; then
  echo "[skip] already running"
  exit 0
fi

menu_cmd=(/usr/bin/jgmenu --simple --config-file "${CONFIG_DIR}/jgmenurc")
menu_file="${CONFIG_DIR}/menu.csv"

root_id=$(/usr/bin/xwininfo -root | awk '/Window id:/{print $4}')
echo "[root] id=${root_id}"

press=0
/usr/bin/xev -root -event button | while IFS= read -r line; do
  if [[ "$line" == *"ButtonPress"* ]]; then
    press=1
    continue
  fi
  if [[ "$line" == *"ButtonRelease"* ]]; then
    press=0
    continue
  fi
  if [[ $press -eq 1 && "$line" == *"button 3"* ]]; then
    win_id_dec=$(/usr/bin/xdotool getmouselocation --shell | awk -F= '/^WINDOW=/{print $2}')
    win_id=$(printf "0x%x" "${win_id_dec}")
    echo "[click] win_dec=${win_id_dec} win_hex=${win_id}"
    if [[ -n "${root_id}" && "${win_id}" == "${root_id}" ]]; then
      echo "[open] jgmenu"
      "${menu_cmd[@]}" < "${menu_file}"
    fi
    press=0
  fi
done
