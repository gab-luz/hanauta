#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NUITKA_DIR="$ROOT/hanauta/bin/nuitka"

popup_targets=(
  "hanauta-ai-popup"
  "hanauta-calendar-popup"
  "hanauta-game-mode-popup"
  "hanauta-hotkeys-overlay"
  "hanauta-launcher"
  "hanauta-ntfy-popup"
  "hanauta-pomodoro-widget"
  "hanauta-powermenu"
  "hanauta-vpn-control"
  "hanauta-weather-popup"
  "hanauta-wifi-control"
  "hanauta-window-switcher"
)

selected=()
if [[ $# -gt 0 ]]; then
  for target in "$@"; do
    for popup_target in "${popup_targets[@]}"; do
      if [[ "$target" == "$popup_target" ]]; then
        selected+=("$target")
        break
      fi
    done
  done
else
  selected=("${popup_targets[@]}")
fi

if [[ ${#selected[@]} -eq 0 ]]; then
  echo "No matching popup targets requested." >&2
  echo "Available targets:" >&2
  printf '  %s\n' "${popup_targets[@]}" >&2
  exit 1
fi

mapfile -t pyqt_files < <(find "$ROOT/hanauta/src/pyqt" -path '*/__pycache__' -prune -o -name '*.py' -print | sort)
python3 -m py_compile "${pyqt_files[@]}"

mkdir -p "$NUITKA_DIR"

for target in "${selected[@]}"; do
  find "$NUITKA_DIR" -maxdepth 1 -type d -name '*.dist' \
    -exec sh -c 'test -x "$1/$2"' _ {} "$target" \; -print \
    | while IFS= read -r dist_dir; do
        rm -rf "$dist_dir"
      done
  rm -f "$ROOT/hanauta/bin/$target"
done

"$ROOT/hanauta/build-nuitka.sh" "${selected[@]}"
