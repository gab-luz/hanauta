#!/usr/bin/env bash
set -euo pipefail

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if need_cmd betterlockscreen; then
  echo "[INFO] betterlockscreen is already installed; skipping."
  exit 0
fi

if ! need_cmd git; then
  echo "[ERROR] git is required to install betterlockscreen."
  exit 1
fi

if ! need_cmd sudo; then
  echo "[ERROR] sudo is required to install betterlockscreen."
  exit 1
fi

if [ -r /etc/os-release ]; then
  . /etc/os-release
else
  ID=""
  ID_LIKE=""
fi

if [ "${ID:-}" = "debian" ] || [ "${ID_LIKE:-}" = "debian" ] || [ "${ID:-}" = "ubuntu" ]; then
  if ! sudo apt-get update -qq; then
    echo "[WARN] apt metadata update had warnings/errors; continuing with current package lists."
  fi
  sudo apt-get install -y i3lock imagemagick x11-xserver-utils x11-utils
elif [ "${ID:-}" = "arch" ] || [ "${ID_LIKE:-}" = "arch" ]; then
  sudo pacman -S --needed --noconfirm i3lock imagemagick xorg-xdpyinfo xorg-xrandr
else
  echo "[ERROR] Unsupported distro for automatic betterlockscreen install."
  exit 1
fi

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT
repo_root="$tmp_root/betterlockscreen"

echo "[INFO] Cloning betterlockscreen..."
git clone --depth 1 https://github.com/betterlockscreen/betterlockscreen.git "$repo_root"

echo "[INFO] Installing betterlockscreen..."
sudo install -Dm755 "$repo_root/betterlockscreen" /usr/local/bin/betterlockscreen
if [ -d "$repo_root/system" ]; then
  sudo mkdir -p /usr/local/share/betterlockscreen
  sudo cp -a "$repo_root/system/." /usr/local/share/betterlockscreen/
fi

if need_cmd betterlockscreen; then
  echo "[OK] betterlockscreen installed successfully."
  exit 0
fi

echo "[ERROR] betterlockscreen install finished but command is still unavailable."
exit 1
