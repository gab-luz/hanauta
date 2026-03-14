#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$ROOT_DIR/bin"
BUILD_DIR="$ROOT_DIR/.build/service"

mkdir -p "$OUT_DIR"
mkdir -p "$BUILD_DIR"

QT6_MOC="${QT6_MOC:-$(qtpaths6 --query QT_HOST_LIBEXECS 2>/dev/null || true)}"
if [ -n "$QT6_MOC" ] && [ -d "$QT6_MOC" ]; then
  QT6_MOC="$QT6_MOC/moc"
fi
if [ -z "${QT6_MOC:-}" ] || [ ! -x "$QT6_MOC" ]; then
  for candidate in /usr/lib/qt6/libexec/moc /usr/lib/qt6/bin/moc /usr/lib64/qt6/libexec/moc /usr/lib/x86_64-linux-gnu/qt6/libexec/moc; do
    if [ -x "$candidate" ]; then
      QT6_MOC="$candidate"
      break
    fi
  done
fi
if [ -z "${QT6_MOC:-}" ] || [ ! -x "$QT6_MOC" ]; then
  echo "Could not find a Qt6 moc binary." >&2
  exit 1
fi

cc_common=(
  -std=c11
  -O2
  -Wall
  -Wextra
  -Wpedantic
)

cxx_common=(
  -std=c++20
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

compile_cpp() {
  local src="$1"
  local out="$2"
  shift 2
  if [ -f "$out" ] && [ "$out" -nt "$src" ]; then
    printf 'Up to date %s\n' "$out"
    return
  fi
  c++ "${cxx_common[@]}" "$src" -o "$out" "$@"
}

compile_qt_cpp() {
  local src="$1"
  local out="$2"
  local moc_out="$3"
  shift 3
  if [ -f "$out" ] && [ "$out" -nt "$src" ]; then
    printf 'Up to date %s\n' "$out"
    return
  fi
  "$QT6_MOC" "$src" -o "$moc_out"
  c++ "${cxx_common[@]}" "$src" -o "$out" "$@"
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

compile_cpp \
  "$ROOT_DIR/src/service/hanauta-clock.cpp" \
  "$OUT_DIR/hanauta-clock" \
  $(pkg-config --cflags --libs Qt6Widgets Qt6Gui Qt6Core)

compile_qt_cpp \
  "$ROOT_DIR/src/service/hanauta-powermenu.cpp" \
  "$OUT_DIR/hanauta-powermenu" \
  "$BUILD_DIR/hanauta-powermenu.moc" \
  -I"$BUILD_DIR" \
  $(pkg-config --cflags --libs Qt6QuickControls2 Qt6Quick Qt6Qml Qt6Gui Qt6Core)

compile_qt_cpp \
  "$ROOT_DIR/src/service/hanauta-notification-center.cpp" \
  "$OUT_DIR/hanauta-notification-center" \
  "$BUILD_DIR/hanauta-notification-center.moc" \
  -I"$BUILD_DIR" \
  $(pkg-config --cflags --libs Qt6QuickControls2 Qt6Quick Qt6Qml Qt6Gui Qt6Core Qt6Network)

printf 'Built %s\n' "$OUT_DIR/hanauta-service"
printf 'Built %s\n' "$OUT_DIR/hanauta-notifyctl"
printf 'Built %s\n' "$OUT_DIR/hanauta-notifyd"
printf 'Built %s\n' "$OUT_DIR/hanauta-clock"
printf 'Built %s\n' "$OUT_DIR/hanauta-powermenu"
printf 'Built %s\n' "$OUT_DIR/hanauta-notification-center"
