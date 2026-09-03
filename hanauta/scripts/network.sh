#!/bin/bash

symbol() {
	[ "$(cat /sys/class/net/w*/operstate)" = down ] && echo 睊 && exit
	echo 
}

name() {
	/sbin/iwgetid -r
}

trim() {
	toshow="$1"
	maxlen="$2"

	sufix=""

	if test $(echo "$toshow" | wc -c) -ge "$maxlen"; then
		sufix=" ..."
	fi

	echo "${toshow:0:$maxlen}$sufix"
}

case "$1" in
	icon)
		symbol
		;;
	ssid)
		ssid=$(name)
		if [[ "$ssid" == "" ]]; then
			trim "Disconnected" 10
		else
			trim "$ssid" 10
		fi
		;;
	name)
		wifiname=$(name)
		if [[ "$wifiname" == "" ]]; then
			echo "Disconnected"
		else
			echo "Connected to $wifiname"
		fi
		;;
	class)
		wifiname=$(name)
		if [[ "$wifiname" == "" ]]; then
			echo "disconnected"
		else
			echo "connected"
		fi
		;;
	status)
		wifiname=$(name)
		if [[ "$wifiname" != "" ]]; then
			echo "Connected"
		else
			echo "Disconnected"
		fi
		;;
	disconnect)
		wifiname=$(iwgetid -r)
		nmcli con down id "${wifiname}"
		;;
	connect)
		nmcli con up ifname "$(/usr/bin/ls /sys/class/ieee80211/*/device/net/)"
		;;
	toggle)
		wifiname=$(name)
		if [[ "$wifiname" == "" ]]; then
			nmcli con up ifname "$(/usr/bin/ls /sys/class/ieee80211/*/device/net/)"
		else
			nmcli con down id "${wifiname}"
		fi
		;;
	radio-status)
		radio_status=$(nmcli radio wifi)
		if [[ "$radio_status" == "enabled" ]]; then
			echo "on"
		else
			echo "off"
		fi
		;;
	toggle-radio)
		radio_status=$(nmcli radio wifi)
		if [[ "$radio_status" == "enabled" ]]; then
			nmcli radio wifi off
		else
			nmcli radio wifi on
		fi
		;;
	signal)
		# Get WiFi signal strength as percentage (0-100)
		DEVICE=$(/usr/bin/ls /sys/class/ieee80211/*/device/net/ 2>/dev/null | head -1)
		if [ -z "$DEVICE" ]; then
			echo "0"
			exit 0
		fi
		SIGNAL=$(nmcli -t -f IN-USE,SIGNAL device wifi list ifname "$DEVICE" 2>/dev/null | grep '^\*' | cut -d: -f2 | head -1)
		if [ -z "$SIGNAL" ]; then
			# Fallback: get signal from iw
			SIGNAL=$(iw dev "$DEVICE" link 2>/dev/null | grep 'signal:' | awk '{print $2}' | sed 's/dBm//')
			if [ -n "$SIGNAL" ]; then
				# Convert dBm to percentage (rough approximation)
				# -30 dBm = 100%, -90 dBm = 0%
				if [ "$SIGNAL" -ge -30 ]; then
					SIGNAL=100
				elif [ "$SIGNAL" -le -90 ]; then
					SIGNAL=0
				else
					SIGNAL=$(( (SIGNAL + 90) * 100 / 60 ))
				fi
			else
				SIGNAL=0
			fi
		fi
		echo "$SIGNAL"
		;;
esac
