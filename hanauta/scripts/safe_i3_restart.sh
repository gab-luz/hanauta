#!/usr/bin/env bash
set -u

I3MSG="$(command -v i3-msg || true)"
if [ -z "$I3MSG" ]; then
  exit 1
fi

# In this environment, the built-in `restart` path is behaving like a
# full session exit. Emulate a safe restart by reloading config and
# relaunching the long-lived Hanauta UI processes.
"$I3MSG" reload >/dev/null 2>&1 || true

# Close settings if it is open so restart behavior matches other shell UIs.
pkill -x hanauta-settings 2>/dev/null || true
pkill -f "$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py" 2>/dev/null || true

"$HOME/.config/i3/startup.sh" >/tmp/i3-startup-wrapper.log 2>&1 &

exit 0
