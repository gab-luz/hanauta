#!/bin/bash

STATE_FILE="/tmp/pomodoro.state"
PID_FILE="/tmp/pomodoro.pid"

get_icon() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
        if [[ "$ACTIVE" == "true" ]]; then
            echo "󰌂"
        else
            echo ""
        fi
    else
        echo ""
    fi
}

get_status() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
        if [[ "$ACTIVE" == "true" ]]; then
            echo "on"
        else
            echo "off"
        fi
    else
        echo "off"
    fi
}

start_pomodoro() {
    echo "ACTIVE=true" > "$STATE_FILE"
    echo "START_TIME=$(date +%s)" >> "$STATE_FILE"
    
    (
        sleep 25m
        
        echo "ACTIVE=false" > "$STATE_FILE"
        rm -f "$PID_FILE"
        
        notify-send -u critical "Pomodoro" "Time's up! Take a break."
        paplay /usr/share/sounds/freedesktop/stereo/complete.ogg 2>/dev/null
    ) &
    
    echo $! > "$PID_FILE"
    notify-send "Pomodoro" "Timer started! 25 minutes."
}

stop_pomodoro() {
    if [[ -f "$PID_FILE" ]]; then
        kill $(cat "$PID_FILE") 2>/dev/null
        rm -f "$PID_FILE"
    fi
    echo "ACTIVE=false" > "$STATE_FILE"
    notify-send "Pomodoro" "Timer stopped."
}

toggle() {
    if [[ -f "$STATE_FILE" ]]; then
        source "$STATE_FILE"
        if [[ "$ACTIVE" == "true" ]]; then
            stop_pomodoro
        else
            start_pomodoro
        fi
    else
        start_pomodoro
    fi
}

case "$1" in
    --icon)
        get_icon
        ;;
    --status)
        get_status
        ;;
    --toggle)
        toggle
        ;;
    *)
        echo "Usage: $0 {--icon|--status|--toggle}"
        ;;
esac
