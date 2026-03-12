#!/usr/bin/env bash
set -Eeuo pipefail

# Builds Raymo111/i3lock-color locally against the current system libraries
# and installs the resulting binary into ~/.config/i3/bin/i3lock-color.
#
# Upstream sources used:
# - https://github.com/Raymo111/i3lock-color
# - README Debian dependency list
# - build.sh / install-i3lock-color.sh

REPO_URL="https://github.com/Raymo111/i3lock-color.git"
ROOT_DIR="${HOME}/.config/i3"
SRC_DIR="${ROOT_DIR}/.cache-src/i3lock-color"
OUT_DIR="${ROOT_DIR}/bin"
OUT_BIN="${OUT_DIR}/i3lock-color"

mkdir -p "${OUT_DIR}"
mkdir -p "$(dirname "${SRC_DIR}")"

echo "[1/4] Installing build dependencies"
sudo apt update
sudo apt install -y \
  autoconf \
  automake \
  gcc \
  make \
  pkg-config \
  libpam0g-dev \
  libcairo2-dev \
  libfontconfig1-dev \
  libxcb-composite0-dev \
  libev-dev \
  libx11-xcb-dev \
  libxcb-xkb-dev \
  libxcb-xinerama0-dev \
  libxcb-randr0-dev \
  libxcb-image0-dev \
  libxcb-util0-dev \
  libxcb-xrm-dev \
  libxkbcommon-dev \
  libxkbcommon-x11-dev \
  libjpeg-dev \
  libgif-dev

echo "[2/4] Fetching upstream source"
if [[ -d "${SRC_DIR}/.git" ]]; then
  git -C "${SRC_DIR}" fetch --tags origin
  git -C "${SRC_DIR}" reset --hard origin/master
else
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

echo "[3/4] Building i3lock-color"
git -C "${SRC_DIR}" tag -f "git-$(git -C "${SRC_DIR}" rev-parse --short HEAD)" >/dev/null 2>&1 || true
(
  cd "${SRC_DIR}"
  chmod +x build.sh
  ./build.sh
)

echo "[4/4] Installing local binary"
install -m 0755 "${SRC_DIR}/build/i3lock" "${OUT_BIN}"

echo
echo "Installed: ${OUT_BIN}"
echo "Test with:"
echo "  ${OUT_BIN} --help"
