#!/usr/bin/env bash

set -eu

CACHE_FILE="/tmp/eww-notifications-cache.json"
PID_FILE="/tmp/eww-notifications-cache.pid"
TMP_FILE="/tmp/eww-notifications-cache.tmp"
INTERVAL="${1:-2}"
LOCAL_NOTIFYCTL="$HOME/.config/i3/bin/hanauta-notifyctl"

if [ -f "$PID_FILE" ]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "${old_pid:-}" ] && kill -0 "$old_pid" 2>/dev/null; then
    exit 0
  fi
fi

printf '%s\n' "$$" >"$PID_FILE"
trap 'rm -f "$PID_FILE" "$TMP_FILE"' EXIT INT TERM

write_cache() {
  local notifyctl_bin="hanauta-notifyctl"
  if [ -x "$LOCAL_NOTIFYCTL" ]; then
    notifyctl_bin="$LOCAL_NOTIFYCTL"
  elif ! command -v hanauta-notifyctl >/dev/null 2>&1; then
    notifyctl_bin=""
  fi

  if [ -z "$notifyctl_bin" ] || ! command -v jq >/dev/null 2>&1; then
    printf '%s\n' '[]' >"$TMP_FILE"
    mv "$TMP_FILE" "$CACHE_FILE"
    return
  fi

  raw="$("$notifyctl_bin" history 2>/dev/null || true)"
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
