#!/usr/bin/env bash

# Outputs a Yuck snippet for the notifications list.

limit=5

if ! command -v hanauta-notifyctl >/dev/null 2>&1; then
  echo "(label :class \"notif-empty\" :text \"Sem notificações\")"
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "(label :class \"notif-empty\" :text \"Sem notificações\")"
  exit 0
fi

raw="$(hanauta-notifyctl history 2>/dev/null)" || raw=""
if [ -z "$raw" ]; then
  echo "(label :class \"notif-empty\" :text \"Sem notificações\")"
  exit 0
fi

echo "$raw" | jq -r --argjson limit "$limit" '
  [ .data[0][]? | {summary: .summary.data, body: .body.data} ] |
  reverse | .[:$limit] |
  if length == 0 then
    "(box :orientation \"v\" (label :class \"notif-empty\" :text \"Sem notificações\"))"
  else
    "(box :orientation \"v\" " +
    (map(
      "(box :class \"notif-item\" :orientation \"v\" " +
      "(label :class \"notif-title\" :text \"" + (.summary | gsub("\""; "\\\"") | gsub("\n"; " ")) + "\") " +
      "(label :class \"notif-body\" :text \"" + (.body | gsub("\""; "\\\"") | gsub("\n"; " · ")) + "\"))"
    ) | join(" ")) +
    ")"
  end
'
