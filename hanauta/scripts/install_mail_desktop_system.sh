#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
SOURCE_DESKTOP="$REPO_ROOT/hanauta/config/applications/hanauta-mail.desktop"
TARGET_DIR="/usr/local/share/applications"
TARGET_DESKTOP="$TARGET_DIR/hanauta-mail.desktop"

if [ ! -f "$SOURCE_DESKTOP" ]; then
  echo "Desktop entry not found at $SOURCE_DESKTOP" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DESKTOP" "$TARGET_DESKTOP"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$TARGET_DIR" >/dev/null 2>&1 || true
fi
