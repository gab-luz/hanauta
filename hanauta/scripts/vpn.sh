#!/bin/bash

WG_CONF_DIR="/etc/wireguard"
STATE_FILE="/tmp/eww_vpn_wg_selected"
ALT_CONF_DIR_FILE="${HOME}/.local/state/hanauta/vpn_conf_dir"
SELECTED_WG="${STATE_FILE}"

json_escape() {
    printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

print_result() {
    local ok="$1"
    local message="$2"
    printf '{"ok":%s,"message":%s}\n' "$ok" "$(json_escape "$message")"
}

get_alt_conf_dir() {
    if [ -f "$ALT_CONF_DIR_FILE" ]; then
        cat "$ALT_CONF_DIR_FILE"
    fi
}

set_alt_conf_dir() {
    local dir="$1"
    [ -n "$dir" ] || return 1
    mkdir -p "$(dirname "$ALT_CONF_DIR_FILE")"
    printf '%s\n' "$dir" > "$ALT_CONF_DIR_FILE"
}

effective_wg_conf_dir() {
    if [ -d "$WG_CONF_DIR" ] && [ -r "$WG_CONF_DIR" ] && ls "$WG_CONF_DIR"/*.conf >/dev/null 2>&1; then
        echo "$WG_CONF_DIR"
        return 0
    fi
    local alt_dir
    alt_dir="$(get_alt_conf_dir)"
    if [ -n "$alt_dir" ] && [ -d "$alt_dir" ] && [ -r "$alt_dir" ] && ls "$alt_dir"/*.conf >/dev/null 2>&1; then
        echo "$alt_dir"
        return 0
    fi
    return 1
}

prompt_for_conf_dir() {
    local selected=""
    if command -v zenity >/dev/null 2>&1; then
        selected="$(zenity --file-selection --directory --title="Select WireGuard config folder" 2>/dev/null || true)"
    elif command -v kdialog >/dev/null 2>&1; then
        selected="$(kdialog --getexistingdirectory "$HOME" "Select WireGuard config folder" 2>/dev/null || true)"
    fi

    selected="$(printf '%s' "$selected" | sed 's/[[:space:]]*$//')"
    if [ -z "$selected" ] || [ ! -d "$selected" ]; then
        print_result false "No folder selected."
        return 1
    fi
    if ! ls "$selected"/*.conf >/dev/null 2>&1; then
        print_result false "No .conf files found in $selected."
        return 1
    fi
    set_alt_conf_dir "$selected"
    print_result true "Using WireGuard configs from $selected."
    return 0
}

get_wg_interfaces() {
    local conf_dir
    conf_dir="$(effective_wg_conf_dir 2>/dev/null || true)"
    if [ -z "$conf_dir" ]; then
        return 0
    fi
    ls "$conf_dir"/*.conf 2>/dev/null | xargs -n1 basename | sed 's/.conf//'
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
    elif get_active_wg_interface | grep -q .; then
        echo "on"
    else
        echo "off"
    fi
}

get_active_wg_interface() {
    if command -v wg >/dev/null 2>&1; then
        wg show interfaces 2>/dev/null | tr ' ' '\n' | while read -r iface; do
            [ -n "$iface" ] || continue
            if ip link show "$iface" 2>/dev/null | grep -q "UP"; then
                echo "$iface"
            fi
        done
        return
    fi
    ip -brief link show type wireguard 2>/dev/null | awk '$3 ~ /UP/ { print $1 }'
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
        select_wg >/dev/null 2>&1 || true
        iface="$(get_selected_wg)"
        if [ -z "$iface" ]; then
            print_result false "No WireGuard interface selected."
            return 1
        fi
    }
    if ! get_wg_interfaces | grep -Fxq "$iface"; then
        print_result false "WireGuard config for $iface was not found."
        return 1
    fi
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
    count=$(printf '%s\n' "$interfaces" | grep -c . || true)
    
    if [ "$count" -eq 0 ]; then
        if prompt_for_conf_dir >/dev/null 2>&1; then
            interfaces=$(get_wg_interfaces)
            count=$(printf '%s\n' "$interfaces" | grep -c . || true)
        fi
    fi

    if [ "$count" -eq 0 ]; then
        notify-send "WireGuard" "No configs found in /etc/wireguard or chosen folder"
        return 1
    fi
    
    if [ "$count" -eq 1 ]; then
        echo "$interfaces" > "$SELECTED_WG"
        notify-send "WireGuard" "Selected: $interfaces"
        return 0
    fi
    
    local selected
    selected=$(echo "$interfaces" | rofi -dmenu -p "Select WireGuard interface" -i -lines "$count")
    if [ -n "$selected" ]; then
        echo "$selected" > "$SELECTED_WG"
        notify-send "WireGuard" "Selected: $selected"
        return 0
    fi
    return 1
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
        ACTIVE_WG=$(get_active_wg_interface | head -1)
        if [ "$WG_STATUS" = "on" ] && [ -n "$ACTIVE_WG" ] && ! ip link show "$SELECTED" 2>/dev/null | grep -q "UP"; then
            SELECTED="$ACTIVE_WG"
        fi
        
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
    --choose-conf-dir)
        prompt_for_conf_dir
        ;;
    --toggle-ts)
        toggle_tailscale
        ;;
    --interfaces)
        get_wg_interfaces
        ;;
    *)
        echo "Usage: $0 {--status|--toggle-wg [iface]|--set-wg iface|--select-wg|--choose-conf-dir|--toggle-ts|--interfaces}"
        ;;
esac
