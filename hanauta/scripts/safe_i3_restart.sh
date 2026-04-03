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

"$HOME/.config/i3/startup.sh" >/tmp/i3-startup-wrapper.log 2>&1 &

exit 0
