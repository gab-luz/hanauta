#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

width="${1:-1920}"
height="${2:-1080}"
out="${3:-$HOME/.cache/hanauta/lockscreen.png}"

mkdir -p "$(dirname "$out")"

# Render QML -> PNG (static frame). This is X11/i3 compatible because betterlockscreen uses a cached image.
QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
  python3 "$SCRIPT_DIR/render_qml_lock.py" \
    --width "$width" \
    --height "$height" \
    --out "$out"

if command -v betterlockscreen >/dev/null 2>&1; then
  betterlockscreen -u "$out"
else
  printf '[INFO] betterlockscreen not found; rendered image at: %s\n' "$out"
fi

