#!/bin/bash

# Prefer xrandr so the same slider can drive all active desktop outputs.

percentage() {
  local val
  val="$(echo "$1" | tr '%' ' ' | awk '{print $1}')"
  local icon1="$2"
  local icon2="$3"
  local icon3="$4"
  local icon4="$5"
  if [ "${val:-0}" -le 15 ]; then
    echo "$icon1"
  elif [ "${val:-0}" -le 30 ]; then
    echo "$icon2"
  elif [ "${val:-0}" -le 60 ]; then
    echo "$icon3"
  else
    echo "$icon4"
  fi
}

list_outputs() {
  local active_outputs

  active_outputs="$(xrandr --listactivemonitors 2>/dev/null | awk 'NR > 1 {print $NF}')"
  if [ -n "$active_outputs" ]; then
    printf '%s\n' "$active_outputs"
    return
  fi

  xrandr --query 2>/dev/null | awk '/ connected / {print $1}'
}

get_brightness_xrandr() {
  local values
  values="$(xrandr --verbose 2>/dev/null | awk '
    $2 == "connected" { connected=1; next }
    $0 !~ /^[[:space:]]/ { connected=0 }
    connected && /Brightness:/ { print $2 }
  ')"

  if [ -z "$values" ]; then
    return 1
  fi

  awk '
    { sum += $1; count += 1 }
    END {
      if (count == 0) {
        exit 1
      }
      printf "%d\n", (sum / count) * 100
    }
  ' <<EOF
$values
EOF
}

get_brightness_backlight() {
  local current max

  current="$(brightnessctl get 2>/dev/null)" || return 1
  max="$(brightnessctl max 2>/dev/null)" || return 1

  if [ -z "$current" ] || [ -z "$max" ] || [ "$max" -le 0 ] 2>/dev/null; then
    return 1
  fi

  echo $(( current * 100 / max ))
}

get_brightness() {
  get_brightness_xrandr || get_brightness_backlight || echo 0
}

set_brightness_xrandr() {
  local percent="$1"
  local brightness
  local output
  local had_output=0

  brightness="$(awk -v p="$percent" 'BEGIN { printf "%.2f\n", p / 100 }')"

  while IFS= read -r output; do
    [ -n "$output" ] || continue
    had_output=1
    xrandr --output "$output" --brightness "$brightness" >/dev/null 2>&1 || return 1
  done <<EOF
$(list_outputs)
EOF

  [ "$had_output" -eq 1 ]
}

set_brightness_backlight() {
  local percent="$1"

  if command -v brightnessctl >/dev/null 2>&1; then
    brightnessctl set "${percent}%" >/dev/null 2>&1 && return 0
  fi

  if command -v light >/dev/null 2>&1; then
    light -S "$percent" >/dev/null 2>&1 && return 0
  fi

  return 1
}

set_brightness() {
  local percent="${1:-0}"

  if ! [[ "$percent" =~ ^[0-9]+$ ]]; then
    percent=0
  fi

  if [ "$percent" -lt 1 ]; then
    percent=1
  elif [ "$percent" -gt 100 ]; then
    percent=100
  fi

  set_brightness_xrandr "$percent" || set_brightness_backlight "$percent"
}

get_percent() {
  echo "$(get_brightness)%"
}

get_icon() {
  local br
  br="$(get_percent)"
  echo "$(percentage "$br" "" "" "" "")"
}

if [[ $1 == "br" ]]; then
  get_brightness
fi

if [[ $1 == "percent" ]]; then
  get_percent
fi

if [[ $1 == "icon" ]]; then
  get_icon
fi

if [[ $1 == "set" ]]; then
  set_brightness "$2"
fi
