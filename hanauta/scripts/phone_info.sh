#!/bin/bash

INDEX_FILE="/tmp/eww_kdeconnect_index"

mapfile -t CONNECTED < <(kdeconnect-cli -a --id-only 2>/dev/null)
CONNECTED_COUNT=${#CONNECTED[@]}

if [ "$CONNECTED_COUNT" -eq 0 ]; then
  if [ "$1" == "--toggle-clip" ]; then
      notify-send "KDE Connect" "You can't toggle clipboard because there's no phone connected"
  fi
  echo '{"name": "Disconnected", "battery": "0", "status": "Offline", "id": "", "clipboard": "off"}'
  exit 0
fi

if [ -f "$INDEX_FILE" ]; then
    INDEX=$(cat "$INDEX_FILE")
else
    INDEX=0
fi

if [ "$1" == "--next" ]; then
    INDEX=$(( (INDEX + 1) % CONNECTED_COUNT ))
    echo "$INDEX" > "$INDEX_FILE"
fi

if [ "$INDEX" -ge "$CONNECTED_COUNT" ]; then
    INDEX=0
    echo "$INDEX" > "$INDEX_FILE"
fi

DEVICE_ID="${CONNECTED[$INDEX]}"
DEVICE_CONFIG_DIR="$HOME/.config/kdeconnect/$DEVICE_ID"
DEVICE_NAME=$(kdeconnect-cli -a --name-only 2>/dev/null | sed -n "$((INDEX + 1))p")

BATTERY=$(busctl --user get-property org.kde.kdeconnect /modules/kdeconnect/devices/"$DEVICE_ID"/battery org.kde.kdeconnect.device.battery charge 2>/dev/null | awk '{print $2}')
[ -z "$BATTERY" ] && BATTERY=$(qdbus org.kde.kdeconnect /modules/kdeconnect/devices/"$DEVICE_ID"/battery org.kde.kdeconnect.device.battery.charge 2>/dev/null)
[ -z "$BATTERY" ] && BATTERY="?"

IS_CHARGING=$(busctl --user get-property org.kde.kdeconnect /modules/kdeconnect/devices/"$DEVICE_ID"/battery org.kde.kdeconnect.device.battery isCharging 2>/dev/null | awk '{print $2}')
[ -z "$IS_CHARGING" ] && IS_CHARGING=$(qdbus org.kde.kdeconnect /modules/kdeconnect/devices/"$DEVICE_ID"/battery org.kde.kdeconnect.device.battery.isCharging 2>/dev/null)
if [ "$IS_CHARGING" == "true" ]; then
    STATUS="Charging"
else
    STATUS="Connected"
fi

CLIP_STATE_FILE="/tmp/eww_kdeconnect_clip_${DEVICE_ID}"

if [ ! -f "$CLIP_STATE_FILE" ]; then
    if [ -f "$DEVICE_CONFIG_DIR/config" ] && grep -q "kdeconnect_clipboardEnabled=true" "$DEVICE_CONFIG_DIR/config" 2>/dev/null; then
        echo "on" > "$CLIP_STATE_FILE"
    else
        echo "off" > "$CLIP_STATE_FILE"
    fi
fi

CLIP_STATE=$(cat "$CLIP_STATE_FILE")

if [ "$1" == "--toggle-clip" ]; then
    if [ "$CLIP_STATE" == "on" ]; then
        CLIP_STATE="off"
        mkdir -p "$DEVICE_CONFIG_DIR"
        echo -e "[Plugins]\nkdeconnect_clipboardEnabled=false" > "$DEVICE_CONFIG_DIR/config"
        notify-send "KDE Connect" "Clipboard sync disabled for $DEVICE_NAME"
    else
        CLIP_STATE="on"
        mkdir -p "$DEVICE_CONFIG_DIR"
        echo -e "[Plugins]\nkdeconnect_clipboardEnabled=true" > "$DEVICE_CONFIG_DIR/config"
        kdeconnect-cli -d "$DEVICE_ID" --refresh 2>/dev/null
        notify-send "KDE Connect" "Clipboard sync enabled for $DEVICE_NAME"
    fi
    echo "$CLIP_STATE" > "$CLIP_STATE_FILE"
fi

echo "{\"name\": \"$DEVICE_NAME\", \"battery\": \"$BATTERY\", \"status\": \"$STATUS\", \"id\": \"$DEVICE_ID\", \"clipboard\": \"$CLIP_STATE\"}"
