#!/bin/sh

APP_CMD="$HOME/.config/i3/ai-chat/run.sh"

if pgrep -f "$APP_CMD" >/dev/null 2>&1 || pgrep -f "python3 $HOME/.config/i3/ai-chat/src/main.py" >/dev/null 2>&1; then
  pkill -f "$APP_CMD" >/dev/null 2>&1
  pkill -f "python3 $HOME/.config/i3/ai-chat/src/main.py" >/dev/null 2>&1
  exit 0
fi

"$APP_CMD" >/tmp/ai-chat.log 2>&1 &
