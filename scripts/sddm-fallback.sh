#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[sddm-fallback] %s\n' "$*"
}

die() {
  printf '[sddm-fallback][error] %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

if ! need_cmd systemctl; then
  die "systemctl is required"
fi

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if need_cmd sudo; then
    exec sudo "$0" "$@"
  fi
  die "run as root (or install sudo)"
fi

PREFERRED_DM="${1:-}"

# DMs we can switch to if installed.
DM_CANDIDATES=(
  lightdm
  gdm
  gdm3
  lxdm
  xdm
  ly
)

service_exists() {
  local svc="$1"
  systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "${svc}.service"
}

enable_and_restart_dm() {
  local dm="$1"
  log "Enabling ${dm}.service"
  systemctl enable "${dm}.service"

  # Stop/disable SDDM first to avoid DM conflicts.
  if service_exists sddm; then
    log "Stopping and disabling sddm.service"
    systemctl disable sddm.service || true
    systemctl stop sddm.service || true
  fi

  log "Restarting ${dm}.service"
  systemctl restart "${dm}.service"
  log "Fallback complete: switched to ${dm}.service"
}

switch_to_tty_safe_mode() {
  log "No alternative display manager found. Switching to safe TTY mode."
  if service_exists sddm; then
    systemctl disable sddm.service || true
    systemctl stop sddm.service || true
  fi
  systemctl set-default multi-user.target
  log "System default target set to multi-user.target"
  log "On next boot you will land in TTY login (no graphical DM)."
  log "To restore graphical boot later: systemctl set-default graphical.target"
}

main() {
  local dm=""

  if [ -n "$PREFERRED_DM" ]; then
    if service_exists "$PREFERRED_DM"; then
      enable_and_restart_dm "$PREFERRED_DM"
      return 0
    fi
    die "Requested display manager '${PREFERRED_DM}' is not installed as a systemd service"
  fi

  for dm in "${DM_CANDIDATES[@]}"; do
    if service_exists "$dm"; then
      enable_and_restart_dm "$dm"
      return 0
    fi
  done

  switch_to_tty_safe_mode
}

main "$@"
