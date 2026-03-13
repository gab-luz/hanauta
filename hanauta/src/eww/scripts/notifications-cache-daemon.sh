#!/usr/bin/env bash

set -eu

CACHE_FILE="/tmp/eww-notifications-cache.json"
PID_FILE="/tmp/eww-notifications-cache.pid"
TMP_FILE="/tmp/eww-notifications-cache.tmp"
INTERVAL="${1:-2}"
LOCAL_DUNSTCTL="$HOME/.config/i3/bin/dunstctl"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "${old_pid:-}" ] && kill -0 "$old_pid" 2>/dev/null; then
    exit 0
  fi
fi

printf '%s\n' "$$" >"$PID_FILE"
trap 'rm -f "$PID_FILE" "$TMP_FILE"' EXIT INT TERM

write_cache() {
  local dunstctl_bin="dunstctl"
  if [ -x "$LOCAL_DUNSTCTL" ]; then
    dunstctl_bin="$LOCAL_DUNSTCTL"
  elif ! command -v dunstctl >/dev/null 2>&1; then
    dunstctl_bin=""
  fi

  if [ -z "$dunstctl_bin" ] || ! command -v jq >/dev/null 2>&1; then
    printf '%s\n' '[]' >"$TMP_FILE"
    mv "$TMP_FILE" "$CACHE_FILE"
    return
  fi

  raw="$("$dunstctl_bin" history 2>/dev/null || true)"
  if [ -z "$raw" ]; then
    printf '%s\n' '[]' >"$TMP_FILE"
    mv "$TMP_FILE" "$CACHE_FILE"
    return
  fi

  printf '%s\n' "$raw" | jq -c '
    [.data[0][]? | {
      appname: (.appname.data // ""),
      summary: (.summary.data // ""),
      body: (.body.data // ""),
      id: (.id.data // 0)
    }] | if length == 0 then [] else . end
  ' >"$TMP_FILE" 2>/dev/null || printf '%s\n' '[]' >"$TMP_FILE"

  mv "$TMP_FILE" "$CACHE_FILE"
}

printf '%s\n' '[]' >"$CACHE_FILE"

while :; do
  write_cache
  sleep "$INTERVAL"
done
