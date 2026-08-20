#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
HANAUTA_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DESKTOP_SOURCE="$HANAUTA_ROOT/config/applications/hanauta-mail.desktop"
LAUNCHER="$HANAUTA_ROOT/scripts/open_hanauta_mail.sh"
DESKTOP_TARGET="/usr/local/share/applications/hanauta-mail.desktop"

if [ ! -f "$DESKTOP_SOURCE" ]; then
  printf 'Hanauta Mail desktop template not found at %s\n' "$DESKTOP_SOURCE" >&2
  exit 1
fi

if [ ! -f "$LAUNCHER" ]; then
  printf 'Hanauta Mail launcher not found at %s\n' "$LAUNCHER" >&2
  exit 1
fi

mkdir -p "$(dirname "$DESKTOP_TARGET")"
chmod +x "$LAUNCHER" 2>/dev/null || true
sed "s|@HANAUTA_MAIL_LAUNCHER@|$LAUNCHER|g" "$DESKTOP_SOURCE" > "$DESKTOP_TARGET"
chmod 0644 "$DESKTOP_TARGET"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$(dirname "$DESKTOP_TARGET")" >/dev/null 2>&1 || true
fi

printf 'Installed %s\n' "$DESKTOP_TARGET"
