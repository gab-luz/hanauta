#!/usr/bin/env bash
set -euo pipefail

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if need_cmd sudo; then
    exec sudo "$0" "$@"
  fi
  echo "[enable-ssh][error] Run as root or install sudo" >&2
  exit 1
fi

if [ -r /etc/os-release ]; then
  . /etc/os-release
fi

if need_cmd apt-get; then
  if ! dpkg -s openssh-server >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y openssh-server
  fi
elif need_cmd pacman; then
  if ! pacman -Q openssh >/dev/null 2>&1; then
    pacman -S --needed --noconfirm openssh
  fi
fi

if systemctl list-unit-files | rg -q '^ssh\.service'; then
  systemctl enable --now ssh.service
  svc='ssh.service'
elif systemctl list-unit-files | rg -q '^sshd\.service'; then
  systemctl enable --now sshd.service
  svc='sshd.service'
else
  echo "[enable-ssh][error] Could not find ssh/sshd systemd unit" >&2
  exit 1
fi

echo "[enable-ssh] Enabled and started ${svc}"
systemctl is-enabled "${svc}"
systemctl is-active "${svc}"
