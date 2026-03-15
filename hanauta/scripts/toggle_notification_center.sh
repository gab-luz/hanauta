#!/usr/bin/env bash

set -eu

CONFIG_DIR="${HOME}/.config/i3/hanauta/src/eww"

(
    if eww -c "$CONFIG_DIR" active-windows 2>/dev/null | grep -q ': notification_center$'; then
        eww -c "$CONFIG_DIR" update notification_center_ready=false
        sleep 0.10
        eww -c "$CONFIG_DIR" close notification_center
    else
        eww -c "$CONFIG_DIR" update notification_center_ready=false
        eww -c "$CONFIG_DIR" open notification_center
        sleep 0.12
        eww -c "$CONFIG_DIR" update notification_center_ready=true
    fi
) >/dev/null 2>&1 &
