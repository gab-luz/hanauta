#!/usr/bin/env bash

status_file="/tmp/eww-gamemode.enabled"

get_status() {
    if [ -f "$status_file" ]; then
        echo "on"
    else
        echo "off"
    fi
}

get_icon() {
    if [ -f "$status_file" ]; then
        echo "󰊖"
    else
        echo "󰊖"
    fi
}

toggle() {
    current=$(get_status)
    if [ "$current" = "on" ]; then
        rm -f "$status_file"
        gamemoded -r
        notify-send "Game Mode" "Disabled" -i "󰊖"
    else
        touch "$status_file"
        gamemoded -r
        notify-send "Game Mode" "Enabled" -i "󰊖"
    fi
}

case "$1" in
    status) get_status ;;
    icon) get_icon ;;
    toggle) toggle ;;
    *) get_status ;;
esac
