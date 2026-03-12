#!/usr/bin/env bash

rofi -modi "clipboard:greenclip print" -theme "$HOME/.config/i3/scripts/clipboard.rasi" -show clipboard -run-command '{cmd}'
