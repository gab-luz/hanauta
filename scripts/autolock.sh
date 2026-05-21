#!/usr/bin/env bash
set -euo pipefail

# Reuse Hanauta's lock entrypoint so autolock never calls i3lock directly.
xautolock -time 2 -locker "$HOME/.config/i3/hanauta/scripts/lock" && echo mem ? /sys/power/state
