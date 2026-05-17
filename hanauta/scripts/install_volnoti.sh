#!/usr/bin/env bash
set -euo pipefail

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if need_cmd volnoti; then
  echo "[INFO] volnoti is already installed; skipping."
  exit 0
fi

if ! need_cmd git; then
  echo "[ERROR] git is required to build volnoti."
  exit 1
fi

if ! need_cmd sudo; then
  echo "[ERROR] sudo is required to install volnoti into /usr."
  exit 1
fi

if [ -r /etc/os-release ]; then
  . /etc/os-release
else
  ID=""
  ID_LIKE=""
fi

if [ "${ID:-}" = "debian" ] || [ "${ID_LIKE:-}" = "debian" ] || [ "${ID:-}" = "ubuntu" ]; then
  sudo apt-get update -qq
  sudo apt-get install -y \
    git build-essential pkg-config autoconf automake libtool \
    libdbus-1-dev libdbus-glib-1-dev libgtk2.0-dev libgdk-pixbuf-2.0-dev
elif [ "${ID:-}" = "arch" ] || [ "${ID_LIKE:-}" = "arch" ]; then
  sudo pacman -S --needed --noconfirm \
    git base-devel pkgconf autoconf automake libtool dbus dbus-glib gtk2 gdk-pixbuf2
else
  echo "[ERROR] Unsupported distro for automatic volnoti build."
  exit 1
fi

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT
repo_root="$tmp_root/volnoti"

echo "[INFO] Cloning volnoti..."
git clone --depth 1 https://github.com/brazdil/volnoti.git "$repo_root"

# Compatibility patch for older source snapshots against newer generated stubs.
if [ -f "$repo_root/src/client.c" ] && [ -f "$repo_root/src/value-client-stub.h" ]; then
  if grep -q 'GError \*\*error)' "$repo_root/src/value-client-stub.h" 2>/dev/null; then
    perl -i -pe 's/\buk_ac_cam_db538_VolumeNotification_notify\s*\([^)]+\);/uk_ac_cam_db538_VolumeNotification_notify(proxy, volume, \&error);/g' "$repo_root/src/client.c"
  fi
fi

echo "[INFO] Building volnoti from source..."
( cd "$repo_root" && ./prepare.sh && ./configure --prefix=/usr && make )

echo "[INFO] Installing volnoti..."
( cd "$repo_root" && sudo make install )

if need_cmd volnoti; then
  echo "[OK] volnoti installed successfully."
  exit 0
fi

echo "[ERROR] volnoti install finished but command is still unavailable."
exit 1
