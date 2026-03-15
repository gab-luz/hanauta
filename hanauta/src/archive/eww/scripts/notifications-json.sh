#!/usr/bin/env bash

set -eu

CACHE_FILE="/tmp/eww-notifications-cache.json"

if [ -s "$CACHE_FILE" ]; then
  cat "$CACHE_FILE"
else
  printf '%s\n' '[]'
fi
