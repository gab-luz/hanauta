from __future__ import annotations

import json
from pathlib import Path

from notif_center.paths import SETTINGS_FILE
from notif_center.utils import _atomic_write_json


DEFAULT_SERVICE_SETTINGS = {
    "kdeconnect": {
        "enabled": True,
        "show_in_notification_center": True,
        "low_battery_fullscreen_notification": False,
        "low_battery_threshold": 20,
    },
    "home_assistant": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "vpn_control": {
        "enabled": True,
        "show_in_notification_center": False,
    },
    "christian_widget": {
        "enabled": False,
        "show_in_notification_center": False,
        "show_in_bar": False,
        "next_devotion_notifications": False,
        "hourly_verse_notifications": False,
    },
    "calendar_widget": {
        "enabled": True,
        "show_in_notification_center": False,
    },
    "reminders_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "pomodoro_widget": {
        "enabled": True,
        "show_in_notification_center": True,
    },
    "rss_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "obs_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "crypto_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "vps_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "desktop_clock_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
    "game_mode_widget": {
        "enabled": False,
        "show_in_notification_center": False,
    },
}


def merged_service_settings(payload: object) -> dict[str, dict]:
    services = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict] = {}
    for key, defaults in DEFAULT_SERVICE_SETTINGS.items():
        current = services.get(key, {}) if isinstance(services, dict) else {}
        if not isinstance(current, dict):
            current = {}
        merged[key] = {
            "enabled": bool(current.get("enabled", defaults["enabled"])),
            "show_in_notification_center": bool(
                current.get("show_in_notification_center", defaults["show_in_notification_center"])
            ),
        }
        if key == "kdeconnect":
            merged[key]["low_battery_fullscreen_notification"] = bool(
                current.get("low_battery_fullscreen_notification", defaults.get("low_battery_fullscreen_notification", False))
            )
            try:
                merged[key]["low_battery_threshold"] = max(1, min(100, int(current.get("low_battery_threshold", defaults.get("low_battery_threshold", 20)))))
            except Exception:
                merged[key]["low_battery_threshold"] = int(defaults.get("low_battery_threshold", 20))
        elif key == "christian_widget":
            merged[key]["show_in_bar"] = bool(current.get("show_in_bar", defaults.get("show_in_bar", False)))
            merged[key]["next_devotion_notifications"] = bool(current.get("next_devotion_notifications", defaults.get("next_devotion_notifications", False)))
            merged[key]["hourly_verse_notifications"] = bool(current.get("hourly_verse_notifications", defaults.get("hourly_verse_notifications", False)))
        elif key == "home_assistant":
            merged[key]["show_in_bar"] = bool(current.get("show_in_bar", defaults.get("show_in_bar", False)))
    return merged


def load_notification_settings() -> dict:
    default = {
        "appearance": {"accent": "orchid"},
        "notification_center": {"width": 800, "height": 740},
        "home_assistant": {"url": "", "token": "", "pinned_entities": []},
        "services": merged_service_settings({}),
        "display": {"layout_mode": "extend", "primary": "", "outputs": []},
        "autolock": {"enabled": True, "timeout_minutes": 2},
        "weather": {"enabled": False, "name": "", "admin1": "", "country": "", "latitude": 0.0, "longitude": 0.0, "timezone": "auto"},
        "ntfy": {
            "enabled": False, "show_in_bar": False, "server_url": "https://ntfy.sh",
            "topic": "", "token": "", "username": "", "password": "", "auth_mode": "token",
            "topics": [], "all_topics": False, "hide_notification_content": False,
        },
    }
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return default
    if not isinstance(payload, dict):
        payload = {}
    appearance = dict(payload.get("appearance", {}))
    appearance.setdefault("accent", "orchid")
    home_assistant = dict(payload.get("home_assistant", {}))
    home_assistant.setdefault("url", "")
    home_assistant.setdefault("token", "")
    pinned = [item for item in home_assistant.get("pinned_entities", []) if isinstance(item, str)][:5]
    home_assistant["pinned_entities"] = pinned
    services = merged_service_settings(payload.get("services", {}))
    display = dict(payload.get("display", {}))
    display.setdefault("layout_mode", "extend")
    display.setdefault("primary", "")
    outputs = display.get("outputs", [])
    display["outputs"] = outputs if isinstance(outputs, list) else []
    autolock = dict(payload.get("autolock", {}))
    autolock["enabled"] = bool(autolock.get("enabled", True))
    try:
        autolock["timeout_minutes"] = max(1, min(60, int(autolock.get("timeout_minutes", 2))))
    except Exception:
        autolock["timeout_minutes"] = 2
    weather = dict(payload.get("weather", {}))
    for k, v in (("enabled", False), ("name", ""), ("admin1", ""), ("country", ""), ("latitude", 0.0), ("longitude", 0.0), ("timezone", "auto")):
        weather.setdefault(k, v)
    ntfy = dict(payload.get("ntfy", {}))
    for k, v in (("enabled", False), ("show_in_bar", False), ("server_url", "https://ntfy.sh"), ("topic", ""), ("token", ""), ("username", ""), ("password", ""), ("auth_mode", "token"), ("topics", []), ("all_topics", False)):
        ntfy.setdefault(k, v)
    ntfy["hide_notification_content"] = bool(ntfy.get("hide_notification_content", False))
    ntfy["topics"] = [str(item).strip() for item in ntfy.get("topics", []) if isinstance(item, str) and str(item).strip()]
    nc = dict(payload.get("notification_center", {}))
    try:
        nc["width"] = max(400, min(2400, int(nc.get("width", 800))))
    except Exception:
        nc["width"] = 800
    try:
        nc["height"] = max(300, min(1600, int(nc.get("height", 740))))
    except Exception:
        nc["height"] = 740
    payload["notification_center"] = nc
    payload["appearance"] = appearance
    payload["home_assistant"] = home_assistant
    payload["services"] = services
    payload["display"] = display
    payload["autolock"] = autolock
    payload["weather"] = weather
    payload["ntfy"] = ntfy
    return payload


def save_notification_settings(settings: dict) -> None:
    _atomic_write_json(SETTINGS_FILE, settings)
