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
esac
