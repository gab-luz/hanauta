#!/bin/sh

status="$("$HOME/.config/i3/hanauta/src/eww/scripts/mpris.sh" status 2>/dev/null)"
if [ "$status" != "Playing" ]; then
  printf '%s\n' '(box :class "cava-widget" (label :class "cava-bar" :text "▁") (label :class "cava-bar" :text "▁") (label :class "cava-bar" :text "▁") (label :class "cava-bar" :text "▁") (label :class "cava-bar" :text "▁") (label :class "cava-bar" :text "▁"))'
  exit 0
fi

track="$("$HOME/.config/i3/hanauta/src/eww/scripts/mpris.sh" title 2>/dev/null)"
artist="$("$HOME/.config/i3/hanauta/src/eww/scripts/mpris.sh" artist 2>/dev/null)"
seed="$(printf '%s%s' "$track" "$artist" | cksum | awk '{print $1}')"
tick="$(date +%s)"
bars='▁ ▂ ▃ ▄ ▅ ▆ ▇ █'
count=6
out='(box :class "cava-widget"'
i=0

while [ "$i" -lt "$count" ]; do
  idx=$(( (seed / (i + 1) + tick + i * 3) % 8 + 1 ))
  glyph="$(printf '%s\n' "$bars" | awk -v n="$idx" '{print $n}')"
  out="$out (label :class \"cava-bar\" :text \"$glyph\")"
  i=$((i + 1))
done

out="$out)"
printf '%s\n' "$out"
