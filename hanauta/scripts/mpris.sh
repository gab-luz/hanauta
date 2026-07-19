#!/usr/bin/env bash

declare -A _player_status_cache

Control=""

pick_player() {
  local players p
  players="$(playerctl -l 2>/dev/null)" || return 1
  [ -z "$players" ] && return 1

  prefer() {
    local status="$1" list="$2"
    for p in $list; do
      [ "$(playerctl --player="$p" status 2>/dev/null)" = "$status" ] && echo "$p" && return 0
    done
    return 1
  }

  local preferred=() others=() mpd=()
  for p in $players; do
    case "$(printf "%s" "$p" | tr '[:upper:]' '[:lower:]')" in
      librewolf*|firefox*|chromium*|brave*|chrome*|vivaldi*)
        preferred+=("$p")
        ;;
      mpd*)
        mpd+=("$p")
        ;;
      *)
        others+=("$p")
        ;;
    esac
  done

  prefer "Playing" "${preferred[*]}" && return 0
  prefer "Playing" "${others[*]}" && return 0
  prefer "Paused" "${preferred[*]}" && return 0
  prefer "Paused" "${others[*]}" && return 0
  [ -n "${preferred[*]}" ] && echo "${preferred[0]}" && return 0
  [ -n "${others[*]}" ] && echo "${others[0]}" && return 0
  [ -n "${mpd[*]}" ] && echo "${mpd[0]}" && return 0
  return 1
}

Control="$(pick_player)"

if [ -n "$Control" ]; then
  _player_status_cache["$Control"]="$(playerctl --player="$Control" status 2>/dev/null)"
fi

default_title="Play Something"
default_artist="Artist"
default_album="Album"
default_status="Stopped"
cover_path="/tmp/cover.png"
bkp_cover="$HOME/.config/i3/assets/fallback.webp"

title() {
  local t
  t="$(playerctl --player="$Control" metadata --format '{{title}}' 2>/dev/null)"
  [ -n "$t" ] && echo "$t" || echo "$default_title"
}

artist() {
  local a
  a="$(playerctl --player="$Control" metadata --format '{{artist}}' 2>/dev/null)"
  [ -n "$a" ] && echo "$a" || echo "$default_artist"
}

album() {
  local a
  a="$(playerctl --player="$Control" metadata --format '{{album}}' 2>/dev/null)"
  [ -n "$a" ] && echo "$a" || echo "$default_album"
}

status() {
  local cached="${_player_status_cache[$Control]}"
  [ -n "$cached" ] && echo "$cached" || echo "$default_status"
}

statusicon() {
  local s icon
  s="${_player_status_cache[$Control]}"
  icon=""
  [ "$s" = "Playing" ] && icon="󰐊"
  [ "$s" = "Paused" ] && icon="󰏤"
  echo "$icon"
}

summary() {
  local raw t a b s
  raw="$(playerctl --player="$Control" metadata --format '{{title}}\x1f{{artist}}\x1f{{album}}' 2>/dev/null)"
  t="$(printf '%s' "$raw" | cut -d $'\x1f' -f1)"
  a="$(printf '%s' "$raw" | cut -d $'\x1f' -f2)"
  b="$(printf '%s' "$raw" | cut -d $'\x1f' -f3)"
  s="$(status)"
  [ -z "$t" ] && t="$default_title"
  [ -z "$a" ] && a="$default_artist"
  [ -z "$b" ] && b="$default_album"
  printf '%s\x1f%s\x1f%s\n' "$t" "$a" "$s"
}

player() {
  [ -n "$Control" ] && echo "$Control"
}

coverloc() {
  local art hash
  art="$(playerctl --player="$Control" metadata mpris:artUrl 2>/dev/null)"
  if [ -n "$art" ]; then
    hash="$(printf '%s' "$art" | md5sum | cut -d' ' -f1)"
    if [ -f "$cover_path" ] && [ -f "/tmp/cover_${hash}.flag" ]; then
      echo "$cover_path"
      return
    fi
    if printf '%s' "$art" | grep -q "^file://"; then
      cp "${art#file://}" "$cover_path" 2>/dev/null || cp "$bkp_cover" "$cover_path"
    else
      curl -s "$art" --output "$cover_path" || cp "$bkp_cover" "$cover_path"
    fi
    touch "/tmp/cover_${hash}.flag"
  else
    cp "$bkp_cover" "$cover_path"
  fi
  echo "$cover_path"
}

if [ -z "$Control" ]; then
  case "$1" in
    player) echo "" ;;
    title) echo "$default_title" ;;
    artist) echo "$default_artist" ;;
    album) echo "$default_album" ;;
    status) echo "$default_status" ;;
    statusicon) echo "" ;;
    summary) printf '%s\x1f%s\x1f%s\n' "$default_title" "$default_artist" "$default_status" ;;
    coverloc) cp "$bkp_cover" "$cover_path" 2>/dev/null; echo "$cover_path" ;;
    *) exit 0 ;;
  esac
  exit 0
fi

case "$1" in
  --next) playerctl --player="$Control" next ;;
  --previous) playerctl --player="$Control" previous ;;
  --toggle) playerctl --player="$Control" play-pause ;;
  --stop) playerctl --player="$Control" stop ;;
  player) player ;;
  title) title ;;
  artist) artist ;;
  album) album ;;
  status) status ;;
  statusicon) statusicon ;;
  summary) summary ;;
  coverloc) coverloc ;;
  *) exit 0 ;;
esac
