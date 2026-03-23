#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
SOURCE_DESKTOP="$REPO_ROOT/hanauta/config/applications/hanauta-mail.desktop"
TARGET_DIR="${HOME}/.local/share/applications"
TARGET_DESKTOP="$TARGET_DIR/hanauta-mail.desktop"
DESKTOP_ID="hanauta-mail.desktop"
SET_FAVORITE=false
SET_MAILTO=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --favorite)
      SET_FAVORITE=true
      ;;
    --mailto)
      SET_MAILTO=true
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [ ! -f "$SOURCE_DESKTOP" ]; then
  echo "Desktop entry not found at $SOURCE_DESKTOP" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DESKTOP" "$TARGET_DESKTOP"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$TARGET_DIR" >/dev/null 2>&1 || true
fi

if [ "$SET_FAVORITE" = true ] && command -v xdg-settings >/dev/null 2>&1; then
  xdg-settings set default-url-scheme-handler mailto "$DESKTOP_ID" >/dev/null 2>&1 || true
fi

if [ "$SET_MAILTO" = true ] && command -v xdg-mime >/dev/null 2>&1; then
  xdg-mime default "$DESKTOP_ID" x-scheme-handler/mailto >/dev/null 2>&1 || true
fi
