#!/bin/bash

get_caps_status() {
    caps=$(xset q | grep "Caps Lock" | awk '{print $3}')
    if [[ "$caps" == "on" ]]; then
        echo "on"
    else
        echo "off"
    fi
}

get_num_status() {
    num=$(xset q | grep "Num Lock" | awk '{print $3}')
    if [[ "$num" == "on" ]]; then
        echo "on"
    else
        echo "off"
    fi
}

get_caps_icon() {
    caps=$(xset q | grep "Caps Lock" | awk '{print $3}')
    if [[ "$caps" == "on" ]]; then
        echo "󰪛"
    else
        echo ""
    fi
}

get_num_icon() {
    num=$(xset q | grep "Num Lock" | awk '{print $3}')
    if [[ "$num" == "on" ]]; then
        echo ""
    else
        echo ""
    fi
}

toggle_caps() {
    xdotool key Caps_Lock
    sleep 0.1
    caps=$(xset q | grep "Caps Lock" | awk '{print $3}')
    if [[ "$caps" == "on" ]]; then
        notify-send -r 12345 "Caps Lock" "Enabled"
    else
        notify-send -r 12345 "Caps Lock" "Disabled"
    fi
}

toggle_num() {
    xdotool key Num_Lock
    sleep 0.1
    num=$(xset q | grep "Num Lock" | awk '{print $3}')
    if [[ "$num" == "on" ]]; then
        notify-send -r 12346 "Num Lock" "Enabled"
    else
        notify-send -r 12346 "Num Lock" "Disabled"
    fi
}

case "$1" in
    --caps-status)
        get_caps_status
        ;;
    --num-status)
        get_num_status
        ;;
    --caps-icon)
        get_caps_icon
        ;;
    --num-icon)
        get_num_icon
        ;;
    --toggle-caps)
        toggle_caps
        ;;
    --toggle-num)
        toggle_num
        ;;
    *)
        echo "Usage: $0 {--caps-status|--num-status|--caps-icon|--num-icon|--toggle-caps|--toggle-num}"
        ;;
esac
