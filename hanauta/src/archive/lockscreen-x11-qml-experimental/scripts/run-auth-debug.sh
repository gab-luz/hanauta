#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-$ROOT_DIR/build}"
LOG_FILE="${HANAUTA_LOCK_DEBUG_LOG:-/tmp/auth_hanauta.log}"

cd "$BUILD_DIR"

exec stdbuf -o0 -e0 env \
  QT_MESSAGE_PATTERN='[%{time hh:mm:ss.zzz}] %{type} %{category}: %{message}' \
  QT_LOGGING_RULES='qt.qml.debug=true;qt.qml.binding.removal.info=true;qt.quick*=true;qt.qpa*=true' \
  QML_IMPORT_TRACE=1 \
  QSG_INFO=1 \
  QT_FATAL_WARNINGS=0 \
  ./auth_hanauta 2>&1 | tee "$LOG_FILE"
