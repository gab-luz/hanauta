#!/bin/bash

WG_CONF_DIR="/etc/wireguard"
STATE_FILE="/tmp/eww_vpn_wg_selected"
SELECTED_WG="${STATE_FILE}"

json_escape() {
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

print_result() {
    local ok="$1"
    local message="$2"
    printf '{"ok":%s,"message":%s}\n' "$ok" "$(json_escape "$message")"
}

get_wg_interfaces() {
    if [ -d "$WG_CONF_DIR" ] && [ -r "$WG_CONF_DIR" ]; then
        ls "$WG_CONF_DIR"/*.conf 2>/dev/null | xargs -n1 basename | sed 's/.conf//'
    else
        echo "wg0"
    fi
}

get_selected_wg() {
    if [ -f "$SELECTED_WG" ]; then
        cat "$SELECTED_WG"
    else
        get_wg_interfaces | head -1
    fi
}

get_wg_status() {
    local iface="$1"
    if [ -z "$iface" ]; then
        iface=$(get_selected_wg)
    fi
    if ip link show "$iface" 2>/dev/null | grep -q "UP"; then
        echo "on"
    else
        echo "off"
    fi
}

get_tailscale_status() {
    if command -v tailscale &>/dev/null; then
        if tailscale status --json 2>/dev/null | grep -q '"BackendState":"Running"'; then
            echo "on"
        else
            echo "off"
        fi
    else
        echo "unavailable"
    fi
}

run_privileged() {
    if command -v pkexec >/dev/null 2>&1; then
        pkexec "$@"
        return $?
    fi
    notify-send "WireGuard" "pkexec is not installed"
    return 127
}

toggle_wg() {
    local iface="${1:-$(get_selected_wg)}"
    [ -n "$iface" ] || {
        print_result false "No WireGuard interface selected."
        return 1
    }
    echo "$iface" > "$SELECTED_WG"
    local output=""
    local status=0
    if ip link show "$iface" 2>/dev/null | grep -q "UP"; then
        output=$(run_privileged wg-quick down "$iface" 2>&1)
        status=$?
        if [ "$status" -eq 0 ]; then
            notify-send "WireGuard" "$iface disabled"
            print_result true "$iface disabled."
        else
            notify-send "WireGuard" "Failed to disable $iface"
            if [ -z "$output" ]; then
                output="Failed to disable $iface. Authentication may have been cancelled."
            fi
            print_result false "$output"
            return "$status"
        fi
    else
        output=$(run_privileged wg-quick up "$iface" 2>&1)
        status=$?
        if [ "$status" -eq 0 ]; then
            notify-send "WireGuard" "$iface enabled"
            print_result true "$iface enabled."
        else
            notify-send "WireGuard" "Failed to enable $iface"
            if [ -z "$output" ]; then
                output="Failed to enable $iface. Authentication may have been cancelled."
            fi
            print_result false "$output"
            return "$status"
        fi
    fi
}

set_wg() {
    local iface="$1"
    [ -n "$iface" ] || return
    if get_wg_interfaces | grep -Fxq "$iface"; then
        echo "$iface" > "$SELECTED_WG"
        notify-send "WireGuard" "Selected: $iface"
    fi
}

select_wg() {
    local interfaces
    interfaces=$(get_wg_interfaces)
    local count
    count=$(echo "$interfaces" | wc -l)
    
    if [ "$count" -eq 0 ]; then
        notify-send "WireGuard" "No configs found in /etc/wireguard"
        return
    fi
    
    if [ "$count" -eq 1 ]; then
        echo "$interfaces" > "$SELECTED_WG"
        notify-send "WireGuard" "Selected: $interfaces"
        return
    fi
    
    local selected
    selected=$(echo "$interfaces" | rofi -dmenu -p "Select WireGuard interface" -i -lines "$count")
    if [ -n "$selected" ]; then
        echo "$selected" > "$SELECTED_WG"
        notify-send "WireGuard" "Selected: $selected"
    fi
}

toggle_tailscale() {
    if ! command -v tailscale &>/dev/null; then
        notify-send "Tailscale" "Tailscale not installed"
        return
    fi
    
    local status=$(get_tailscale_status)
    if [ "$status" == "on" ]; then
        if run_privileged tailscale down; then
            notify-send "Tailscale" "Disconnected"
        else
            notify-send "Tailscale" "Failed to disconnect"
        fi
    else
        if run_privileged tailscale up; then
            notify-send "Tailscale" "Connected"
        else
            notify-send "Tailscale" "Failed to connect"
        fi
    fi
}

case "$1" in
    --status)
        WG_STATUS=$(get_wg_status)
        TS_STATUS=$(get_tailscale_status)
        SELECTED=$(get_selected_wg)
        
        echo "{\"wireguard\": \"$WG_STATUS\", \"tailscale\": \"$TS_STATUS\", \"wg_selected\": \"$SELECTED\"}"
        ;;
    --toggle-wg)
        toggle_wg "$2"
        ;;
    --set-wg)
        set_wg "$2"
        ;;
    --select-wg)
        select_wg
        ;;
    --toggle-ts)
        toggle_tailscale
        ;;
    --interfaces)
        get_wg_interfaces
        ;;
    *)
        echo "Usage: $0 {--status|--toggle-wg [iface]|--set-wg iface|--select-wg|--toggle-ts|--interfaces}"
        ;;
esac
