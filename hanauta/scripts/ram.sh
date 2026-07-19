#!/usr/bin/env bash
percentage () {
  local val="${1%%\%}"
  local icon1=$2
  local icon2=$3
  local icon3=$4
  local icon4=$5
  if [ "$val" -le 15 ]; then
    echo $icon1
  elif [ "$val" -le 30 ]; then
    echo $icon2
  elif [ "$val" -le 60 ]; then
    echo $icon3
  else
    echo $icon4
  fi
}

get_ram () {
  awk '/^Mem:/{printf "%d", $3*100/$2}' <(free -m)
}

get_percent () {
  echo $(get_ram)%
}

get_icon () {
  local percent=$(get_percent)
  echo $(percentage "$percent" "")
}

get_class () {
  local percent=$(get_percent)
  echo $(percentage "$percent" "yellow" "magenta" "purple" "red")
}

case "$1" in
  ram) get_ram ;;
  percent) get_percent ;;
  icon) get_icon ;;
  class) get_class ;;
esac
