#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/.config/i3/jgmenu"

# Only open jgmenu when right-clicking on the root window (desktop).
root_id=$(xwininfo -root | awk '/Window id:/{print $4}')
win_id_dec=$(xdotool getmouselocation --shell | awk -F= '/^WINDOW=/{print $2}')
win_id=$(printf "0x%x" "${win_id_dec}")

if [[ -n "${root_id}" && "${win_id}" == "${root_id}" ]]; then
  jgmenu --simple --config-file "${CONFIG_DIR}/jgmenurc" < "${CONFIG_DIR}/menu.csv"
fi
