#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)"
BIN_DIR="$ROOT_DIR/hanauta/bin"
RENDER_BIN="$BIN_DIR/hanauta-lockscreen-render"
SRC_CPP="$SCRIPT_DIR/render_qml_lock.cpp"

width="${1:-1920}"
height="${2:-1080}"
out="${3:-/tmp/hanauta/lockscreen.png}"

mkdir -p "$(dirname "$out")"

mkdir -p "$BIN_DIR"

needs_build=0
if [ ! -x "$RENDER_BIN" ]; then
  needs_build=1
elif [ "$SRC_CPP" -nt "$RENDER_BIN" ]; then
  needs_build=1
fi

if [ "$needs_build" -eq 1 ]; then
  if ! command -v g++ >/dev/null 2>&1; then
    printf '[ERROR] g++ not found; cannot build renderer binary.\n' >&2
    exit 1
  fi
  if ! command -v pkg-config >/dev/null 2>&1; then
    printf '[ERROR] pkg-config not found; cannot build renderer binary.\n' >&2
    exit 1
  fi
  printf '[INFO] Building renderer binary: %s\n' "$RENDER_BIN"
  g++ -O2 -std=c++20 -o "$RENDER_BIN" "$SRC_CPP" \
    $(pkg-config --cflags --libs Qt6Core Qt6Gui Qt6Qml Qt6Quick Qt6QuickControls2)
fi

# Render QML -> PNG (static frame). This is X11/i3 compatible because betterlockscreen uses a cached image.
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
  "$RENDER_BIN" \
    --qml "$SCRIPT_DIR/Lockscreen.qml" \
    --width "$width" \
    --height "$height" \
    --out "$out"

if command -v betterlockscreen >/dev/null 2>&1; then
  # betterlockscreen updates cache under ~/.cache and expects an X display.
  if [ -n "${DISPLAY:-}" ] && [ -w "$HOME/.cache" ]; then
    betterlockscreen -u "$out"
  else
    printf '[INFO] Skipping betterlockscreen cache update (needs writable ~/.cache and DISPLAY). Rendered image at: %s\n' "$out"
  fi
else
  printf '[INFO] betterlockscreen not found; rendered image at: %s\n' "$out"
fi
