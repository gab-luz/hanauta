#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$ROOT_DIR/bin"

mkdir -p "$OUT_DIR"

cc_common=(
  -std=c11
  -O2
  -Wall
  -Wextra
  -Wpedantic
)

compile() {
  local src="$1"
  local out="$2"
  shift 2
  if [ -f "$out" ] && [ "$out" -nt "$src" ]; then
    printf 'Up to date %s\n' "$out"
    return
  fi
  cc "${cc_common[@]}" "$src" -o "$out" "$@"
}

compile \
  "$ROOT_DIR/src/service/hanauta-service.c" \
  "$OUT_DIR/hanauta-service" \
  $(pkg-config --cflags --libs gio-2.0 glib-2.0 gobject-2.0)

compile \
  "$ROOT_DIR/src/service/hanauta-notifyctl.c" \
  "$OUT_DIR/hanauta-notifyctl" \
  $(pkg-config --cflags --libs gio-2.0 glib-2.0 gobject-2.0)

compile \
  "$ROOT_DIR/src/service/hanauta-notifyd.c" \
  "$OUT_DIR/hanauta-notifyd" \
  $(pkg-config --cflags --libs gtk+-3.0 gio-2.0 glib-2.0 gobject-2.0)

printf 'Built %s\n' "$OUT_DIR/hanauta-service"
printf 'Built %s\n' "$OUT_DIR/hanauta-notifyctl"
printf 'Built %s\n' "$OUT_DIR/hanauta-notifyd"
