#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mapfile -t pyqt_files < <(find "$ROOT/hanauta/src/pyqt" -path '*/__pycache__' -prune -o -name '*.py' -print | sort)

if [[ ${#pyqt_files[@]} -eq 0 ]]; then
  echo "No PyQt files found under $ROOT/hanauta/src/pyqt" >&2
  exit 1
fi

python3 -m py_compile "${pyqt_files[@]}"

if [[ $# -eq 0 ]]; then
  find "$ROOT/hanauta/bin/nuitka" -maxdepth 1 -type d -name '*.dist' -exec rm -rf {} +
  find "$ROOT/hanauta/bin" -maxdepth 1 \( -type l -o -type f \) -name 'hanauta-*' -delete
else
  for target in "$@"; do
    find "$ROOT/hanauta/bin/nuitka" -maxdepth 1 -type d -name '*.dist' \
      -exec sh -c 'test -x "$1/$2"' _ {} "$target" \; -print \
      | while IFS= read -r dist_dir; do
          rm -rf "$dist_dir"
        done
    rm -f "$ROOT/hanauta/bin/$target"
  done
fi

"$ROOT/hanauta/build-nuitka.sh" "$@"
