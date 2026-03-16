#!/usr/bin/env bash

set -euo pipefail

THEME_NAME="${1:-}"
SOURCE_DIR="${2:-}"

if [ -z "$THEME_NAME" ] || [ -z "$SOURCE_DIR" ]; then
  echo "Usage: $0 <theme-name> <source-dir>" >&2
  exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "Theme source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

TARGET_ROOT="/usr/share/themes"
TARGET_DIR="$TARGET_ROOT/$THEME_NAME"

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET_DIR"
cp -a "$SOURCE_DIR" "$TARGET_DIR"
