#!/usr/bin/env bash
set -Eeuo pipefail

# bash script for local Debian 13
# This builds a standalone binary with Nuitka.
# For fish shell, run it from bash: bash ./build_hanauta_lock.sh

APP_NAME="hanauta_lock"
SRC_FILE="hanauta_lock.py"
VENV_DIR=".venv-build"
OUT_DIR="dist"
BUILD_CACHE_GLOB="${APP_NAME}.build"

if [[ ! -f "$SRC_FILE" ]]; then
  echo "[erro] nao achei $SRC_FILE no diretorio atual"
  echo "copie o arquivo Python para esta pasta e rode novamente"
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  build-essential \
  patchelf \
  ccache \
  libgl1 \
  libegl1 \
  libxkbcommon0 \
  libfontconfig1 \
  libdbus-1-3

python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip wheel setuptools
python -m pip install nuitka ordered-set zstandard pyqt6

rm -rf "$OUT_DIR" "$BUILD_CACHE_GLOB" .nuitka-cache

python -m nuitka \
  --standalone \
  --enable-plugin=pyqt6 \
  --assume-yes-for-downloads \
  --remove-output \
  --output-dir="$OUT_DIR" \
  --output-filename="$APP_NAME" \
  "$SRC_FILE"

echo
printf '[ok] binario gerado em: %s/%s.dist/%s\n' "$OUT_DIR" "$APP_NAME" "$APP_NAME"
echo '[ok] para testar:'
printf '  export HANAUTA_LOCK_PASSWORD="sua_senha_teste"\n'
printf '  ./%s/%s.dist/%s\n' "$OUT_DIR" "$APP_NAME" "$APP_NAME"
