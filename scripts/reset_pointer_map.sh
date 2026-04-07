#!/usr/bin/env bash
set -euo pipefail

if ! command -v xmodmap >/dev/null 2>&1; then
  exit 0
fi

button_count="$((xmodmap -pp 2>/dev/null || true) | awk '/There are [0-9]+ pointer buttons defined\./ {print $3; exit}')"

if [[ -z "${button_count}" || ! "${button_count}" =~ ^[0-9]+$ ]]; then
  button_count=10
fi

map_line="$(seq -s ' ' 1 "${button_count}")"
xmodmap -e "pointer = ${map_line}" >/dev/null 2>&1 || true
