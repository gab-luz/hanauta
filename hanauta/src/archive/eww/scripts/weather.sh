#!/bin/bash

CONFIG_FILE="$HOME/.config/i3/weather.conf"

load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    fi
}

save_config() {
    echo "CITY=\"$CITY\"" > "$CONFIG_FILE"
}

get_weather_icon() {
    local code=$1
    case $code in
        0) echo "" ;;  # Clear sky
        1) echo "󰖕" ;;  # Mainly clear
        2) echo "󰖐" ;;  # Partly cloudy
        3) echo "󰽰" ;;  # Overcast
        45|48) echo "󰖑" ;;  # Fog
        51|53|55|56|57) echo "󰖗" ;;  # Drizzle
        61|63|65|66|67|80|81|82) echo "󰖘" ;;  # Rain
        71|73|75|77|85|86) echo "󰼶" ;;  # Snow
        95|96|99) echo "󰼵" ;;  # Thunderstorm
        *) echo "" ;;
    esac
}

validate_city() {
    local city="$1"
    
    GEO_JSON=$(curl -s "https://geocoding-api.open-meteo.com/v1/search?name=$city&count=1")
    LAT=$(echo "$GEO_JSON" | jq -r '.results[0].latitude // empty')
    
    if [[ -z "$LAT" ]]; then
        echo "error"
        return 1
    fi
    echo "ok"
    return 0
}

get_weather() {
    load_config
    
    if [[ -z "$CITY" ]]; then
        echo ""
        return
    fi
    
    GEO_JSON=$(curl -s "https://geocoding-api.open-meteo.com/v1/search?name=$CITY&count=1")
    LAT=$(echo "$GEO_JSON" | jq -r '.results[0].latitude // empty')
    LON=$(echo "$GEO_JSON" | jq -r '.results[0].longitude // empty')
    
    if [[ -z "$LAT" || -z "$LON" ]]; then
        echo ""
        return
    fi
    
    WEATHER_JSON=$(curl -s "https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&current_weather=true")
    CODE=$(echo "$WEATHER_JSON" | jq -r '.current_weather.weathercode // -1')
    
    if [[ "$CODE" == "-1" ]]; then
        echo ""
        return
    fi
    
    get_weather_icon "$CODE"
}

set_city() {
    local new_city="$1"
    
    if ! validate_city "$new_city"; then
        echo "invalid"
        return 1
    fi
    
    CITY="$new_city"
    save_config
    get_weather
    echo "ok"
}

get_saved_city() {
    load_config
    echo "$CITY"
}

case "$1" in
    --get)
        get_weather
        ;;
    --set)
        set_city "$2"
        ;;
    --get-city)
        get_saved_city
        ;;
    *)
        echo "Usage: $0 {--get|--set <city>|--get-city}"
        ;;
esac
