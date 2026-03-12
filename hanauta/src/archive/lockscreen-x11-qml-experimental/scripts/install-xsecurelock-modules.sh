#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-$ROOT_DIR/build}"
DEST_DIR="${2:-$HOME/.local/libexec/xsecurelock}"

mkdir -p "$DEST_DIR"
install -m 0755 "$BUILD_DIR/auth_hanauta" "$DEST_DIR/auth_hanauta"
install -m 0755 "$BUILD_DIR/saver_hanauta" "$DEST_DIR/saver_hanauta"

printf 'Installed modules to %s\n' "$DEST_DIR"
printf 'Launch with:\n'
printf '  env XSECURELOCK_AUTH=%s/auth_hanauta XSECURELOCK_AUTHPROTO=%s XSECURELOCK_SAVER=%s/saver_hanauta xsecurelock\n' \
  "$DEST_DIR" \
  "${XSECURELOCK_AUTHPROTO:-/usr/libexec/xsecurelock/authproto_pam}" \
  "$DEST_DIR"
