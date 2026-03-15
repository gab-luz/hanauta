#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"
BIN_DIR="$ROOT/hanauta/bin"
NUITKA_DIR="$BIN_DIR/nuitka"
PYQT_SRC="$ROOT/hanauta/src"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtualenv python at $VENV_PYTHON" >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --disable-pip-version-check -q nuitka ordered-set zstandard

mkdir -p "$NUITKA_DIR"

entries=(
  "hanauta/src/pyqt/shared/action_notification.py:hanauta-action-notification"
  "hanauta/src/pyqt/ai-popup/ai_popup.py:hanauta-ai-popup"
  "hanauta/src/pyqt/bar/ui_bar.py:hanauta-bar"
  "hanauta/src/pyqt/control-center/control_center.py:hanauta-control-center"
  "hanauta/src/pyqt/dock/dock.py:hanauta-dock"
  "hanauta/src/pyqt/launcher/launcher.py:hanauta-launcher"
  "hanauta/src/pyqt/notification-center/notification_center.py:hanauta-notification-center"
  "hanauta/src/pyqt/notification-daemon/notification_daemon.py:hanauta-notification-daemon"
  "hanauta/src/pyqt/powermenu/powermenu.py:hanauta-powermenu"
  "hanauta/src/pyqt/settings-page/settings.py:hanauta-settings"
  "hanauta/src/pyqt/widget-calendar/calendar_popup.py:hanauta-calendar-popup"
  "hanauta/src/pyqt/widget-calendar/qcal-wrapper.py:hanauta-qcal-wrapper"
  "hanauta/src/pyqt/widget-crypto/crypto_widget.py:hanauta-crypto-widget"
  "hanauta/src/pyqt/widget-desktop-clock/desktop_clock_widget.py:hanauta-clock"
  "hanauta/src/pyqt/widget-game-mode/game_mode_popup.py:hanauta-game-mode-popup"
  "hanauta/src/pyqt/widget-hotkeys-overlay/hotkeys_overlay.py:hanauta-hotkeys-overlay"
  "hanauta/src/pyqt/widget-ntfy-control/ntfy_popup.py:hanauta-ntfy-popup"
  "hanauta/src/pyqt/widget-obs/obs_widget.py:hanauta-obs-widget"
  "hanauta/src/pyqt/widget-pomodoro/pomodoro_widget.py:hanauta-pomodoro-widget"
  "hanauta/src/pyqt/widget-religion-christian/christian_widget.py:hanauta-christian-widget"
  "hanauta/src/pyqt/widget-reminders/reminders_widget.py:hanauta-reminders-widget"
  "hanauta/src/pyqt/widget-rss/rss_widget.py:hanauta-rss-widget"
  "hanauta/src/pyqt/widget-vpn-control/vpn_control.py:hanauta-vpn-control"
  "hanauta/src/pyqt/widget-vps/vps_widget.py:hanauta-vps-widget"
  "hanauta/src/pyqt/widget-weather/weather_popup.py:hanauta-weather-popup"
  "hanauta/src/pyqt/widget-wifi-control/wifi_control.py:hanauta-wifi-control"
  "hanauta/src/pyqt/widget-window-switcher/window_switcher.py:hanauta-window-switcher"
)

requested=("$@")
selected_entries=()

for entry in "${entries[@]}"; do
  script_rel="${entry%%:*}"
  name="${entry##*:}"
  if [[ ${#requested[@]} -gt 0 ]]; then
    matched=false
    for requested_name in "${requested[@]}"; do
      if [[ "$requested_name" == "$name" || "$requested_name" == "$script_rel" ]]; then
        matched=true
        break
      fi
    done
    if [[ "$matched" != true ]]; then
      continue
    fi
  fi
  selected_entries+=("$entry")
done

if [[ ${#selected_entries[@]} -eq 0 ]]; then
  echo "No matching Nuitka targets requested." >&2
  exit 1
fi

render_progress() {
  local current="$1"
  local total="$2"
  local label="$3"
  local width=28
  local filled=0
  local empty=0
  local i

  if (( total > 0 )); then
    filled=$(( current * width / total ))
  fi
  empty=$(( width - filled ))

  printf '[%d/%d] [' "$current" "$total"
  for ((i = 0; i < filled; i++)); do
    printf '#'
  done
  for ((i = 0; i < empty; i++)); do
    printf '-'
  done
  printf '] %s\n' "$label"
}

total_entries="${#selected_entries[@]}"
current_entry=0

for entry in "${selected_entries[@]}"; do
  current_entry=$((current_entry + 1))
  script_rel="${entry%%:*}"
  name="${entry##*:}"
  script_path="$ROOT/$script_rel"
  script_stem="$(basename "${script_rel%.py}")"
  dist_exe="$NUITKA_DIR/$script_stem.dist/$name"

  if [[ ! -f "$script_path" ]]; then
    render_progress "$current_entry" "$total_entries" "skipping missing $name"
    echo "Skipping missing script: $script_path" >&2
    continue
  fi
  if [[ -x "$dist_exe" ]]; then
    render_progress "$current_entry" "$total_entries" "reusing $name"
    ln -sfn "nuitka/$script_stem.dist/$name" "$BIN_DIR/$name"
    continue
  fi

  render_progress "$current_entry" "$total_entries" "building $name"

  rm -rf \
    "$NUITKA_DIR/$name.build" \
    "$NUITKA_DIR/$script_stem.build" \
    "$NUITKA_DIR/$script_stem.dist" \
    "$NUITKA_DIR/$name.onefile-build" \
    "$NUITKA_DIR/$script_stem.onefile-build"

  PYTHONPATH="$PYQT_SRC${PYTHONPATH:+:$PYTHONPATH}" "$VENV_PYTHON" -m nuitka \
    --standalone \
    --enable-plugin=pyqt6 \
    --follow-imports \
    --assume-yes-for-downloads \
    --remove-output \
    --jobs="$(nproc)" \
    --output-dir="$NUITKA_DIR" \
    --output-filename="$name" \
    "$script_path"

  ln -sfn "nuitka/$script_stem.dist/$name" "$BIN_DIR/$name"
done

ln -sfn ../../assets "$BIN_DIR/assets"
ln -sfn ../scripts "$BIN_DIR/scripts"
ln -sfn ../../config "$BIN_DIR/config"
ln -sfn .. "$BIN_DIR/hanauta"
