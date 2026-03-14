#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone PyQt6 settings screen inspired by the Hanauta settings mock.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import random
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from urllib import error, request
from urllib import parse
import locale as pylocale

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, Qt, QThread, QTimer, QStringListModel, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QCheckBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.weather import WeatherCity, configured_city, search_cities

ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"
WALLS_DIR = ROOT / "hanauta" / "walls"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"
QCAL_WRAPPER = APP_DIR / "pyqt" / "widget-calendar" / "qcal-wrapper.py"
WALLPAPER_SCRIPT = ROOT / "hanauta" / "src" / "eww" / "scripts" / "set_wallpaper.sh"
MATUGEN_SCRIPT = ROOT / "hanauta" / "src" / "eww" / "scripts" / "run_matugen.sh"
CURRENT_WALLPAPER = Path.home() / ".wallpapers" / "wallpaper.png"
RENDERED_WALLPAPER_DIR = Path.home() / ".wallpapers" / "rendered"
WALLPAPER_SOURCE_CACHE_DIR = ROOT / "hanauta" / "vendor" / "wallpaper-sources"
COMMUNITY_WALLPAPER_DIR = ROOT / "hanauta" / "walls" / "community"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PICOM_CONFIG_FILE = ROOT / "picom.conf"
PYQT_THEME_DIR = Path.home() / ".local" / "state" / "hanauta" / "theme"
PYQT_THEME_FILE = PYQT_THEME_DIR / "pyqt_palette.json"
PICOM_DEFAULT_CONFIG = """backend = "glx";
vsync = true;
use-damage = true;
detect-rounded-corners = true;
detect-client-opacity = true;
detect-transient = true;
mark-wmwin-focused = true;
mark-ovredir-focused = true;
log-level = "warn";

shadow = true;
shadow-radius = 18;
shadow-opacity = 0.18;
shadow-offset-x = -12;
shadow-offset-y = -12;
shadow-color = "#000000";

fading = false;
inactive-opacity = 1.0;
active-opacity = 1.0;
inactive-opacity-override = false;

corner-radius = 18;
transparent-clipping = false;
corner-radius-rules = [
  "88:name = 'PyQt Notification Center'"
];
shadow-exclude = [
  "class_g = 'Eww'",
  "window_type = 'dock'",
  "class_g = 'Rofi'",
  "class_g = 'Conky'",
  "name = 'Hanauta Desktop Clock'",
];

rounded-corners-exclude = [
  "window_type = 'dock'",
  "class_g = 'Rofi'",
  "class_g = 'Conky'",
  "class_g = 'mpv'",
  "name = 'PyQt Notification Center'",
  "name = 'Hanauta Desktop Clock'"
  
];

opacity-rule = [
  "100:class_g = 'Eww'",
  "100:class_g = 'Alacritty'",
  "100:class_g = 'kitty'",
  "100:name = 'PyQt Notification Center'"
];

wintypes:
{
  tooltip = { fade = false; shadow = false; focus = true; full-shadow = false; };
  dock = { shadow = false; clip-shadow-above = true; };
  dnd = { shadow = false; };
  popup_menu = { shadow = false; };
  dropdown_menu = { shadow = false; };
};
"""

WALLPAPER_SOURCE_PRESETS = {
    "caelestia": {
        "label": "Caelestia shell",
        "repo": "https://github.com/caelestia-dots/shell.git",
        "subdirs": ["assets"],
    },
    "end4": {
        "label": "End-4 dots-hyprland",
        "repo": "https://github.com/end-4/dots-hyprland.git",
        "subdirs": ["dots/.config/quickshell/ii/assets/images"],
    },
}

MATERIAL_ICONS = {
    "close": "\ue5cd",
    "menu": "\ue5d2",
    "palette": "\ue40a",
    "tune": "\ue429",
    "grid_view": "\ue9b0",
    "crop_square": "\ue3be",
    "settings": "\ue8b8",
    "image": "\ue3f4",
    "auto_awesome": "\ue65f",
    "photo_library": "\ue413",
    "folder_open": "\ue2c8",
    "light_mode": "\ue518",
    "dark_mode": "\ue51c",
    "opacity": "\ue91c",
    "dock_to_left": "\ue7e6",
    "web_asset": "\ue069",
    "public": "\ue80b",
    "language": "\ue894",
    "widgets": "\ue1bd",
    "bolt": "\uea0b",
    "desktop_windows": "\ue30c",
    "flip": "\ue3e8",
    "sync": "\ue627",
    "shadow": "\ue9df",
    "refresh": "\ue5d5",
    "restart_alt": "\uf053",
    "expand_more": "\ue5cf",
    "home": "\ue88a",
    "hub": "\uee20",
    "lock": "\ue897",
    "notifications": "\ue7f4",
    "notifications_active": "\ue7f7",
    "person": "\ue7fd",
    "partly_cloudy_day": "\uf172",
    "calendar_month": "\ue935",
    "event_upcoming": "\ue614",
    "schedule": "\ue8b5",
    "alarm": "\ue855",
    "timer": "\ue425",
    "coffee": "\uefef",
    "auto_awesome": "\ue65f",
    "rss_feed": "\ue0e5",
    "videocam": "\ue04b",
    "sensors": "\ue51e",
    "storage": "\ue1db",
    "show_chart": "\ue6e1",
    "terminal": "\ue31c",
    "watch": "\ue334",
}


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


DEFAULT_BAR_SETTINGS = {
    "launcher_offset": 0,
    "workspace_offset": 0,
    "datetime_offset": 0,
    "media_offset": 0,
    "status_offset": 0,
    "bar_height": 45,
    "chip_radius": 0,
    "merge_all_chips": False,
    "full_bar_radius": 18,
}


def merged_bar_settings(payload: object) -> dict[str, int]:
    current = payload if isinstance(payload, dict) else {}
    merged = dict(DEFAULT_BAR_SETTINGS)
    offset_keys = {"launcher_offset", "workspace_offset", "datetime_offset", "media_offset", "status_offset"}
    radius_keys = {"chip_radius", "full_bar_radius"}
    for key, default in DEFAULT_BAR_SETTINGS.items():
        if key == "merge_all_chips":
            merged[key] = bool(current.get(key, default)) if isinstance(current, dict) else bool(default)
            continue
        try:
            merged[key] = int(current.get(key, default)) if isinstance(current, dict) else int(default)
        except Exception:
            merged[key] = int(default)
        if key in offset_keys:
            merged[key] = max(-8, min(8, int(merged[key])))
        elif key == "bar_height":
            merged[key] = max(32, min(72, int(merged[key])))
        elif key in radius_keys:
            merged[key] = max(0, min(32, int(merged[key])))
    return merged


DEFAULT_SERVICE_SETTINGS = {
    "home_assistant": {
        "enabled": True,
        "show_in_notification_center": True,
    },
    "vpn_control": {
        "enabled": True,
        "show_in_notification_center": False,
        "reconnect_on_login": False,
        "preferred_interface": "",
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
        "show_in_bar": False,
    },
    "pomodoro_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "rss_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "obs_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "crypto_widget": {
        "enabled": True,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
    "vps_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
    "desktop_clock_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
}


def merged_service_settings(payload: object) -> dict[str, dict[str, bool]]:
    services = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict[str, bool]] = {}
    for key, defaults in DEFAULT_SERVICE_SETTINGS.items():
        current = services.get(key, {}) if isinstance(services, dict) else {}
        if not isinstance(current, dict):
            current = {}
        merged[key] = {"enabled": bool(current.get("enabled", defaults["enabled"]))}
        merged[key]["show_in_notification_center"] = bool(
            current.get(
                "show_in_notification_center",
                defaults["show_in_notification_center"],
            )
        )
        if key == "christian_widget":
            merged[key]["show_in_bar"] = bool(
                current.get(
                    "show_in_bar",
                    current.get(
                        "show_in_notification_center",
                        defaults.get("show_in_bar", False),
                    ),
                )
            )
            merged[key]["next_devotion_notifications"] = bool(
                current.get(
                    "next_devotion_notifications",
                    defaults.get("next_devotion_notifications", False),
                )
            )
            merged[key]["hourly_verse_notifications"] = bool(
                current.get(
                    "hourly_verse_notifications",
                    defaults.get("hourly_verse_notifications", False),
                )
            )
        elif key == "vpn_control":
            merged[key]["reconnect_on_login"] = bool(
                current.get("reconnect_on_login", defaults.get("reconnect_on_login", False))
            )
            merged[key]["preferred_interface"] = str(
                current.get("preferred_interface", defaults.get("preferred_interface", ""))
            ).strip()
        elif key == "reminders_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key == "pomodoro_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
        elif key in {"rss_widget", "obs_widget", "crypto_widget"}:
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
    return merged


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
        "ui_sans": FONTS_DIR / "GoogleSans-Regular.ttf",
        "ui_sans_medium": FONTS_DIR / "GoogleSans-Medium.ttf",
        "ui_display": FONTS_DIR / "GoogleSansDisplay-Regular.ttf",
        "ui_display_medium": FONTS_DIR / "GoogleSansDisplay-Medium.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def run_text(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout.strip()
    except Exception:
        return ""


def load_settings_state() -> dict:
    default = {
        "appearance": {
            "accent": "orchid",
            "wallpaper_mode": "picture",
            "wallpaper_path": str(CURRENT_WALLPAPER),
            "wallpaper_fit_modes": {},
            "slideshow_folder": str(WALLS_DIR),
            "slideshow_interval": 30,
            "slideshow_enabled": False,
            "theme_mode": "dark",
            "transparency": True,
            "use_matugen_palette": False,
        },
        "home_assistant": {
            "url": "",
            "token": "",
            "pinned_entities": [],
        },
        "ntfy": {
            "enabled": False,
            "show_in_bar": False,
            "server_url": "https://ntfy.sh",
            "topic": "",
            "token": "",
            "username": "",
            "password": "",
        },
        "weather": {
            "enabled": False,
            "name": "",
            "admin1": "",
            "country": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": "auto",
        },
        "calendar": {
            "show_week_numbers": False,
            "show_other_month_days": True,
            "first_day_of_week": "monday",
            "caldav_url": "",
            "caldav_username": "",
            "caldav_password": "",
            "last_sync_status": "",
            "connected": False,
        },
        "reminders": {
            "default_lead_minutes": 20,
            "default_intensity": "discrete",
            "tracked_events": [],
            "tea_label": "Tea",
            "tea_minutes": 5,
        },
        "pomodoro": {
            "work_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "long_break_every": 4,
            "auto_start_breaks": False,
            "auto_start_focus": False,
        },
        "rss": {
            "feed_urls": "",
            "opml_source": "",
            "username": "",
            "password": "",
            "item_limit": 10,
            "check_interval_minutes": 15,
            "notify_new_items": True,
        },
        "obs": {
            "host": "127.0.0.1",
            "port": 4455,
            "password": "",
            "auto_connect": False,
        },
        "crypto": {
            "api_provider": "coingecko",
            "api_key": "",
            "tracked_coins": "bitcoin,ethereum",
            "vs_currency": "usd",
            "check_interval_minutes": 15,
            "chart_days": 7,
            "notify_price_moves": True,
            "price_up_percent": 3.0,
            "price_down_percent": 3.0,
        },
        "vps": {
            "host": "",
            "port": 22,
            "username": "",
            "identity_file": "",
            "app_service": "",
            "health_command": "uptime && df -h /",
            "update_command": "sudo apt update && sudo apt upgrade -y",
        },
        "clock": {
            "size": 320,
            "show_seconds": True,
            "position_x": -1,
            "position_y": -1,
        },
        "display": {
            "layout_mode": "extend",
            "primary": "",
            "outputs": [],
        },
    "region": {
        "locale_code": "",
        "use_24_hour": False,
        "date_style": "us",
        "temperature_unit": "c",
    },
    "bar": dict(DEFAULT_BAR_SETTINGS),
    "services": merged_service_settings({}),
    }
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return default
    appearance = dict(payload.get("appearance", {}))
    appearance.setdefault("accent", "orchid")
    appearance.setdefault("wallpaper_mode", "picture")
    appearance.setdefault("wallpaper_path", str(CURRENT_WALLPAPER))
    appearance.setdefault("wallpaper_fit_modes", {})
    appearance.setdefault("slideshow_folder", str(WALLS_DIR))
    appearance.setdefault("slideshow_interval", 30)
    appearance.setdefault("slideshow_enabled", False)
    appearance.setdefault("theme_mode", "dark")
    appearance.setdefault("transparency", True)
    appearance.setdefault("use_matugen_palette", False)
    home_assistant = dict(payload.get("home_assistant", {}))
    home_assistant.setdefault("url", "")
    home_assistant.setdefault("token", "")
    home_assistant.setdefault("pinned_entities", [])
    ntfy = dict(payload.get("ntfy", {}))
    ntfy.setdefault("enabled", False)
    ntfy.setdefault("show_in_bar", False)
    ntfy.setdefault("server_url", "https://ntfy.sh")
    ntfy.setdefault("topic", "")
    ntfy.setdefault("token", "")
    ntfy.setdefault("username", "")
    ntfy.setdefault("password", "")
    weather = dict(payload.get("weather", {}))
    weather.setdefault("enabled", False)
    weather.setdefault("name", "")
    weather.setdefault("admin1", "")
    weather.setdefault("country", "")
    weather.setdefault("latitude", 0.0)
    weather.setdefault("longitude", 0.0)
    weather.setdefault("timezone", "auto")
    calendar = dict(payload.get("calendar", {}))
    calendar.setdefault("show_week_numbers", False)
    calendar.setdefault("show_other_month_days", True)
    first_day = str(calendar.get("first_day_of_week", "monday")).strip().lower()
    calendar["first_day_of_week"] = first_day if first_day in {"monday", "sunday"} else "monday"
    calendar.setdefault("caldav_url", "")
    calendar.setdefault("caldav_username", "")
    calendar.setdefault("caldav_password", "")
    calendar.setdefault("last_sync_status", "")
    calendar.setdefault("connected", False)
    reminders = dict(payload.get("reminders", {}))
    try:
        reminders["default_lead_minutes"] = max(0, min(240, int(reminders.get("default_lead_minutes", 20))))
    except Exception:
        reminders["default_lead_minutes"] = 20
    default_intensity = str(reminders.get("default_intensity", "discrete")).strip().lower()
    reminders["default_intensity"] = default_intensity if default_intensity in {"quiet", "discrete", "disturbing"} else "discrete"
    reminders["tea_label"] = str(reminders.get("tea_label", "Tea")).strip() or "Tea"
    try:
        reminders["tea_minutes"] = max(1, min(180, int(reminders.get("tea_minutes", 5))))
    except Exception:
        reminders["tea_minutes"] = 5
    tracked = reminders.get("tracked_events", [])
    if not isinstance(tracked, list):
        tracked = []
    sanitized_tracked: list[dict] = []
    for item in tracked:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        start = str(item.get("start", "")).strip()
        if not title or not start:
            continue
        try:
            lead_minutes = max(0, min(240, int(item.get("lead_minutes", reminders["default_lead_minutes"]))))
        except Exception:
            lead_minutes = reminders["default_lead_minutes"]
        severity = str(item.get("severity", reminders["default_intensity"])).strip().lower()
        if severity not in {"quiet", "discrete", "disturbing"}:
            severity = reminders["default_intensity"]
        sanitized_tracked.append(
            {
                "title": title,
                "start": start,
                "lead_minutes": lead_minutes,
                "severity": severity,
                "calendar_index": int(item.get("calendar_index", -1)) if str(item.get("calendar_index", "")).strip() else -1,
                "filename": str(item.get("filename", "")).strip(),
            }
        )
    reminders["tracked_events"] = sanitized_tracked
    pomodoro = dict(payload.get("pomodoro", {}))
    try:
        pomodoro["work_minutes"] = max(5, min(90, int(pomodoro.get("work_minutes", 25))))
    except Exception:
        pomodoro["work_minutes"] = 25
    try:
        pomodoro["short_break_minutes"] = max(1, min(30, int(pomodoro.get("short_break_minutes", 5))))
    except Exception:
        pomodoro["short_break_minutes"] = 5
    try:
        pomodoro["long_break_minutes"] = max(5, min(60, int(pomodoro.get("long_break_minutes", 15))))
    except Exception:
        pomodoro["long_break_minutes"] = 15
    try:
        pomodoro["long_break_every"] = max(2, min(8, int(pomodoro.get("long_break_every", 4))))
    except Exception:
        pomodoro["long_break_every"] = 4
    pomodoro["auto_start_breaks"] = bool(pomodoro.get("auto_start_breaks", False))
    pomodoro["auto_start_focus"] = bool(pomodoro.get("auto_start_focus", False))
    rss = dict(payload.get("rss", {}))
    rss["feed_urls"] = str(rss.get("feed_urls", "")).strip()
    rss["opml_source"] = str(rss.get("opml_source", "")).strip()
    rss["username"] = str(rss.get("username", "")).strip()
    rss["password"] = str(rss.get("password", ""))
    try:
        rss["item_limit"] = max(3, min(30, int(rss.get("item_limit", 10))))
    except Exception:
        rss["item_limit"] = 10
    try:
        rss["check_interval_minutes"] = max(5, min(180, int(rss.get("check_interval_minutes", 15))))
    except Exception:
        rss["check_interval_minutes"] = 15
    rss["notify_new_items"] = bool(rss.get("notify_new_items", True))
    obs = dict(payload.get("obs", {}))
    obs["host"] = str(obs.get("host", "127.0.0.1")).strip() or "127.0.0.1"
    try:
        obs["port"] = max(1, min(65535, int(obs.get("port", 4455))))
    except Exception:
        obs["port"] = 4455
    obs["password"] = str(obs.get("password", ""))
    obs["auto_connect"] = bool(obs.get("auto_connect", False))
    crypto = dict(payload.get("crypto", {}))
    crypto["api_provider"] = "coingecko"
    crypto["api_key"] = str(crypto.get("api_key", "")).strip()
    crypto["tracked_coins"] = str(crypto.get("tracked_coins", "bitcoin,ethereum")).strip()
    crypto["vs_currency"] = str(crypto.get("vs_currency", "usd")).strip().lower() or "usd"
    try:
        crypto["check_interval_minutes"] = max(5, min(180, int(crypto.get("check_interval_minutes", 15))))
    except Exception:
        crypto["check_interval_minutes"] = 15
    try:
        crypto["chart_days"] = max(1, min(90, int(crypto.get("chart_days", 7))))
    except Exception:
        crypto["chart_days"] = 7
    crypto["notify_price_moves"] = bool(crypto.get("notify_price_moves", True))
    try:
        crypto["price_up_percent"] = max(0.5, min(50.0, float(crypto.get("price_up_percent", 3.0))))
    except Exception:
        crypto["price_up_percent"] = 3.0
    try:
        crypto["price_down_percent"] = max(0.5, min(50.0, float(crypto.get("price_down_percent", 3.0))))
    except Exception:
        crypto["price_down_percent"] = 3.0
    vps = dict(payload.get("vps", {}))
    vps["host"] = str(vps.get("host", "")).strip()
    try:
        vps["port"] = max(1, min(65535, int(vps.get("port", 22))))
    except Exception:
        vps["port"] = 22
    vps["username"] = str(vps.get("username", "")).strip()
    vps["identity_file"] = str(vps.get("identity_file", "")).strip()
    vps["app_service"] = str(vps.get("app_service", "")).strip()
    vps["health_command"] = str(vps.get("health_command", "uptime && df -h /")).strip() or "uptime && df -h /"
    vps["update_command"] = str(vps.get("update_command", "sudo apt update && sudo apt upgrade -y")).strip() or "sudo apt update && sudo apt upgrade -y"
    clock = dict(payload.get("clock", {}))
    try:
        clock["size"] = max(220, min(520, int(clock.get("size", 320))))
    except Exception:
        clock["size"] = 320
    clock["show_seconds"] = bool(clock.get("show_seconds", True))
    try:
        clock["position_x"] = int(clock.get("position_x", -1))
    except Exception:
        clock["position_x"] = -1
    try:
        clock["position_y"] = int(clock.get("position_y", -1))
    except Exception:
        clock["position_y"] = -1
    display = dict(payload.get("display", {}))
    display.setdefault("layout_mode", "extend")
    display.setdefault("primary", "")
    outputs = display.get("outputs", [])
    if not isinstance(outputs, list):
        outputs = []
    display["outputs"] = [item for item in outputs if isinstance(item, dict)]
    region = dict(payload.get("region", {}))
    region["locale_code"] = str(region.get("locale_code", "")).strip()
    region["use_24_hour"] = bool(region.get("use_24_hour", False))
    date_style = str(region.get("date_style", "us")).strip().lower()
    region["date_style"] = date_style if date_style in {"us", "iso", "eu"} else "us"
    temp_unit = str(region.get("temperature_unit", "c")).strip().lower()
    region["temperature_unit"] = temp_unit if temp_unit in {"c", "f"} else "c"
    bar = merged_bar_settings(payload.get("bar", {}))
    services = merged_service_settings(payload.get("services", {}))
    return {
        "appearance": appearance,
        "home_assistant": home_assistant,
        "ntfy": ntfy,
        "weather": weather,
        "calendar": calendar,
        "reminders": reminders,
        "pomodoro": pomodoro,
        "rss": rss,
        "obs": obs,
        "crypto": crypto,
        "vps": vps,
        "clock": clock,
        "display": display,
        "region": region,
        "bar": bar,
        "services": services,
    }


def save_settings_state(settings: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def ensure_settings_state() -> None:
    save_settings_state(load_settings_state())


def restore_saved_wallpaper() -> None:
    settings = load_settings_state()
    appearance = settings.get("appearance", {})
    wallpaper_path = Path(str(appearance.get("wallpaper_path", ""))).expanduser()
    if not wallpaper_path.exists() or not wallpaper_path.is_file():
        wallpaper_path = CURRENT_WALLPAPER
    if not wallpaper_path.exists() or not wallpaper_path.is_file():
        return

    active_displays = [display for display in parse_xrandr_state() if display.get("enabled")]
    if not active_displays:
        if WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
        else:
            run_bg(["feh", "--bg-fill", str(wallpaper_path)])
        return

    source = QImage(str(wallpaper_path))
    if source.isNull():
        if WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
        else:
            run_bg(["feh", "--bg-fill", str(wallpaper_path)])
        return

    fit_modes = appearance.get("wallpaper_fit_modes", {})
    if not isinstance(fit_modes, dict):
        fit_modes = {}

    rendered_paths: list[Path] = []
    RENDERED_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    for display in active_displays:
        mode_text = str(display.get("current_mode", ""))
        if "x" not in mode_text:
            continue
        try:
            width_text, height_text = mode_text.split("x", 1)
            width = int(width_text)
            height = int(height_text)
        except Exception:
            continue
        canvas = QImage(width, height, QImage.Format.Format_RGB32)
        canvas.fill(QColor("#0E0C12"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        draw_wallpaper_mode(
            painter,
            source,
            width,
            height,
            str(fit_modes.get(str(display.get("name", "")), "fill")),
        )
        painter.end()
        target = RENDERED_WALLPAPER_DIR / f"{sanitize_output_name(str(display.get('name', 'display')))}.png"
        canvas.save(str(target), "PNG")
        rendered_paths.append(target)

    if rendered_paths:
        run_bg(["feh", "--bg-fill", *[str(path) for path in rendered_paths]])
    elif WALLPAPER_SCRIPT.exists():
        run_bg([str(WALLPAPER_SCRIPT), str(wallpaper_path)])
    else:
        run_bg(["feh", "--bg-fill", str(wallpaper_path)])


def restore_saved_vpn() -> None:
    settings = load_settings_state()
    services = settings.get("services", {})
    if not isinstance(services, dict):
        return
    vpn = services.get("vpn_control", {})
    if not isinstance(vpn, dict):
        return
    if not bool(vpn.get("enabled", True)) or not bool(vpn.get("reconnect_on_login", False)):
        return
    iface = str(vpn.get("preferred_interface", "")).strip()
    if not iface:
        return
    vpn_script = ROOT / "hanauta" / "src" / "eww" / "scripts" / "vpn.sh"
    if not vpn_script.exists():
        return
    status_raw = run_text([str(vpn_script), "--status"])
    try:
        status = json.loads(status_raw) if status_raw else {}
    except Exception:
        status = {}
    if (
        isinstance(status, dict)
        and str(status.get("wireguard", "")).strip() == "on"
        and str(status.get("wg_selected", "")).strip() == iface
    ):
        return
    run_bg([str(vpn_script), "--toggle-wg", iface])


def build_display_command(displays: list[dict], primary_name: str, layout_mode: str) -> list[str]:
    cmd = ["xrandr"]
    ordered = sorted(displays, key=lambda item: (item["name"] != primary_name, item["name"]))
    previous_enabled: str | None = None
    for display in ordered:
        cmd.extend(["--output", str(display["name"])])
        if not display.get("enabled"):
            cmd.append("--off")
            continue
        resolution = str(display.get("resolution", "")).strip()
        modes = [str(mode) for mode in display.get("modes", [])]
        if not resolution and modes:
            resolution = modes[0]
        if resolution:
            cmd.extend(["--mode", resolution])
        refresh = str(display.get("refresh", "")).strip()
        if refresh and refresh != "Auto":
            cmd.extend(["--rate", refresh])
        cmd.extend(["--rotate", str(display.get("orientation", "normal")) or "normal"])
        if display["name"] == primary_name:
            cmd.append("--primary")
        if previous_enabled and layout_mode == "extend":
            cmd.extend(["--right-of", previous_enabled])
        elif previous_enabled and layout_mode == "duplicate":
            cmd.extend(["--same-as", primary_name])
        previous_enabled = str(display["name"])
    return cmd


def restore_saved_displays() -> None:
    settings = load_settings_state()
    display_state = settings.get("display", {})
    if not isinstance(display_state, dict):
        return
    saved_outputs = display_state.get("outputs", [])
    if not isinstance(saved_outputs, list) or not saved_outputs:
        return

    current = parse_xrandr_state()
    if not current:
        return
    available = {str(item.get("name", "")): item for item in current}
    restored: list[dict] = []
    for saved in saved_outputs:
        if not isinstance(saved, dict):
            continue
        name = str(saved.get("name", "")).strip()
        if not name or name not in available:
            continue
        current_item = available[name]
        restored.append(
            {
                "name": name,
                "enabled": bool(saved.get("enabled", current_item.get("enabled", True))),
                "resolution": str(saved.get("resolution", current_item.get("current_mode", ""))),
                "refresh": str(saved.get("refresh", "Auto")),
                "orientation": str(saved.get("orientation", current_item.get("orientation", "normal"))),
                "modes": list(current_item.get("modes", [])),
            }
        )
    if not restored:
        return

    enabled = [display for display in restored if display.get("enabled")]
    if not enabled:
        return
    primary_name = str(display_state.get("primary", "")).strip() or str(enabled[0]["name"])
    if primary_name not in {str(display["name"]) for display in enabled}:
        primary_name = str(enabled[0]["name"])
    layout_mode = str(display_state.get("layout_mode", "extend"))
    if layout_mode not in {"extend", "duplicate"}:
        layout_mode = "extend"

    if layout_mode == "duplicate" and len(enabled) > 1:
        common_modes = set(str(mode) for mode in enabled[0].get("modes", []))
        for display in enabled[1:]:
            common_modes &= set(str(mode) for mode in display.get("modes", []))
        if not common_modes:
            layout_mode = "extend"
        else:
            primary_display = next(display for display in enabled if str(display["name"]) == primary_name)
            if str(primary_display.get("resolution", "")) not in common_modes:
                primary_display["resolution"] = sorted(common_modes, key=resolution_area, reverse=True)[0]
            for display in enabled:
                display["resolution"] = primary_display["resolution"]
                if str(display["name"]) != primary_name:
                    display["refresh"] = "Auto"

    cmd = build_display_command(restored, primary_name, layout_mode)
    subprocess.run(cmd, capture_output=True, text=True, check=False)


def accent_palette(name: str) -> dict[str, str]:
    palettes = {
        "orchid": {"accent": "#D0BCFF", "on_accent": "#381E72", "soft": "rgba(208,188,255,0.18)"},
        "mint": {"accent": "#8FE3CF", "on_accent": "#11352D", "soft": "rgba(143,227,207,0.18)"},
        "sunset": {"accent": "#FFB59E", "on_accent": "#4D2418", "soft": "rgba(255,181,158,0.18)"},
    }
    return palettes.get(name, palettes["orchid"])


def normalize_ha_url(url: str) -> str:
    return url.strip().rstrip("/")


def fetch_home_assistant_json(base_url: str, token: str, path: str) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=3.5) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def send_ntfy_message(
    server_url: str,
    topic: str,
    title: str,
    message: str,
    token: str = "",
    username: str = "",
    password: str = "",
) -> tuple[bool, str]:
    base = (server_url or "").strip().rstrip("/")
    channel = (topic or "").strip()
    if not base:
        return False, "Server URL is required."
    if not channel:
        return False, "Topic is required."
    if not message.strip():
        return False, "Message body is required."
    url = f"{base}/{parse.quote(channel)}"
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    if title.strip():
        headers["Title"] = title.strip()
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    req = request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
    if username.strip() or password.strip():
        credentials = f"{username.strip()}:{password}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {encoded}")
    try:
        with request.urlopen(req, timeout=8) as response:
            response.read()
        return True, "ntfy message sent."
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        return False, detail or f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def format_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def resolution_area(mode: str) -> int:
    try:
        width, height = mode.split("x", 1)
        return int(width) * int(height)
    except Exception:
        return 0


def parse_xrandr_state() -> list[dict]:
    output = run_text(["xrandr", "--query"])
    if not output:
        return []

    displays: list[dict] = []
    current: dict | None = None
    for line in output.splitlines():
        if not line.startswith(" "):
            current = None
            if " connected" not in line or "disconnected" in line:
                continue
            name = line.split()[0]
            primary = " connected primary" in line
            geom_match = re.search(r"(\d+x\d+)\+\d+\+\d+", line)
            orient_match = re.search(r"\b(normal|left|right|inverted)\b", line)
            current = {
                "name": name,
                "primary": primary,
                "enabled": bool(geom_match),
                "current_mode": geom_match.group(1) if geom_match else "",
                "current_refresh": "",
                "orientation": orient_match.group(1) if orient_match else "normal",
                "x": 0,
                "y": 0,
                "modes": [],
                "refresh_rates": {},
            }
            if geom_match:
                dims = geom_match.group(0)
                _, pos_x, pos_y = re.match(r"(\d+x\d+)\+(-?\d+)\+(-?\d+)", dims).groups()
                current["x"] = int(pos_x)
                current["y"] = int(pos_y)
            displays.append(current)
            continue
        if current is None:
            continue
        match = re.match(r"^\s+(\d+x\d+)\s+(.+)$", line)
        if not match:
            continue
        mode = match.group(1)
        current["modes"].append(mode)
        refreshes: list[str] = []
        for token in match.group(2).split():
            clean = token.replace("*", "").replace("+", "")
            if re.fullmatch(r"\d+(?:\.\d+)?", clean):
                refreshes.append(clean)
                if "*" in token:
                    current["current_refresh"] = clean
                    current["current_mode"] = mode
        current["refresh_rates"][mode] = refreshes

    for display in displays:
        if not display["current_mode"] and display["modes"]:
            display["current_mode"] = display["modes"][0]
        if display["current_mode"] and not display["enabled"]:
            display["enabled"] = True
    return displays


def read_picom_text() -> str:
    try:
        return PICOM_CONFIG_FILE.read_text(encoding="utf-8")
    except Exception:
        return PICOM_DEFAULT_CONFIG


def parse_picom_settings(text: str) -> dict[str, object]:
    defaults: dict[str, object] = {
        "backend": "glx",
        "vsync": True,
        "use-damage": True,
        "shadow": True,
        "shadow-radius": 18,
        "shadow-opacity": 0.18,
        "shadow-offset-x": -12,
        "shadow-offset-y": -12,
        "fading": False,
        "active-opacity": 1.0,
        "inactive-opacity": 1.0,
        "corner-radius": 18,
        "transparent-clipping": False,
        "detect-rounded-corners": True,
    }

    def find_value(key: str) -> str | None:
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*(.+?);\s*$"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    parsed = dict(defaults)
    for key, default in defaults.items():
        value = find_value(key)
        if value is None:
            continue
        if isinstance(default, bool):
            parsed[key] = value.lower() == "true"
        elif isinstance(default, int):
            try:
                parsed[key] = int(float(value))
            except Exception:
                parsed[key] = default
        elif isinstance(default, float):
            try:
                parsed[key] = float(value)
            except Exception:
                parsed[key] = default
        else:
            parsed[key] = value.strip('"')
    return parsed


def format_picom_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".") if "." in f"{value:.2f}" else str(value)
    return str(value)


def update_picom_config(text: str, values: dict[str, object]) -> str:
    updated = text
    for key, value in values.items():
        line = f"{key} = {format_picom_value(value)};"
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=\s*.+?;\s*$"
        if re.search(pattern, updated):
            updated = re.sub(pattern, line, updated)
        else:
            updated = f"{line}\n{updated}"
    return updated


def write_default_pyqt_palette(use_matugen: bool = False) -> None:
    PYQT_THEME_DIR.mkdir(parents=True, exist_ok=True)
    PYQT_THEME_FILE.write_text(
        json.dumps(
            {
                "use_matugen": use_matugen,
                "source": "#D0BCFF",
                "primary": "#D0BCFF",
                "on_primary": "#381E72",
                "primary_container": "#4F378B",
                "on_primary_container": "#EADDFF",
                "secondary": "#CCC2DC",
                "on_secondary": "#332D41",
                "tertiary": "#EFB8C8",
                "on_tertiary": "#492532",
                "background": "#141218",
                "on_background": "#E6E0E9",
                "surface": "#141218",
                "on_surface": "#E6E0E9",
                "surface_container": "#211F26",
                "surface_container_high": "#2B2930",
                "surface_variant": "#49454F",
                "on_surface_variant": "#CAC4D0",
                "outline": "#938F99",
                "error": "#F2B8B5",
                "on_error": "#601410",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def wallpaper_candidates(folder: Path) -> list[Path]:
    return recursive_wallpaper_candidates(folder)


def recursive_wallpaper_candidates(folder: Path) -> list[Path]:
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def file_sha1(path: Path) -> str | None:
    digest = hashlib.sha1()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def load_json_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def nested_dict_value(payload: dict, *keys: str) -> object | None:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def expand_wallpaper_dir(path_value: object) -> Path | None:
    if not isinstance(path_value, str):
        return None
    text = path_value.strip()
    if not text:
        return None
    return Path(os.path.expandvars(text)).expanduser()


def caelestia_wallpaper_dirs(cache_dir: Path) -> list[Path]:
    shell_config = Path.home() / ".config" / "caelestia" / "shell.json"
    config = load_json_file(shell_config)
    configured_dir = expand_wallpaper_dir(nested_dict_value(config, "paths", "wallpaperDir"))
    env_dir = expand_wallpaper_dir(os.environ.get("CAELESTIA_WALLPAPERS_DIR"))
    candidates = [
        configured_dir,
        env_dir,
        Path.home() / "Wallpaper-Bank" / "wallpapers",
        Path.home() / "Wallpaper-Bank",
        Path.home() / "Pictures" / "Wallpapers" / "showcase",
        Path.home() / "Pictures" / "Wallpapers",
        cache_dir / "assets",
    ]
    results: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    return results


def end4_wallpaper_dirs(cache_dir: Path) -> list[Path]:
    shell_config = Path.home() / ".config" / "illogical-impulse" / "config.json"
    config = load_json_file(shell_config)
    configured_file = expand_wallpaper_dir(nested_dict_value(config, "background", "wallpaperPath"))
    configured_dir = configured_file.parent if configured_file and configured_file.suffix else configured_file
    candidates = [
        configured_dir,
        Path.home() / "Wallpaper-Bank" / "wallpapers",
        Path.home() / "Wallpaper-Bank",
        Path.home() / "Pictures" / "Wallpapers" / "showcase",
        Path.home() / "Pictures" / "Wallpapers",
        cache_dir / "dots" / ".config" / "quickshell" / "ii" / "assets" / "images",
    ]
    results: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    return results


def wallpaper_source_directories(source_key: str, cache_dir: Path) -> list[Path]:
    if source_key == "caelestia":
        return caelestia_wallpaper_dirs(cache_dir)
    if source_key == "end4":
        return end4_wallpaper_dirs(cache_dir)

    preset = WALLPAPER_SOURCE_PRESETS.get(source_key, {})
    return [cache_dir / str(subdir) for subdir in preset.get("subdirs", [])]


def sync_wallpaper_source_preset(source_key: str) -> tuple[bool, str, Path | None]:
    preset = WALLPAPER_SOURCE_PRESETS.get(source_key)
    if not preset:
        return False, "Wallpaper source preset is missing.", None

    repo_url = str(preset.get("repo", "")).strip()
    if not repo_url:
        return False, "Wallpaper source repository is missing.", None

    cache_dir = WALLPAPER_SOURCE_CACHE_DIR / source_key
    target_dir = COMMUNITY_WALLPAPER_DIR / source_key
    WALLPAPER_SOURCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COMMUNITY_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if (cache_dir / ".git").exists():
            fetch = subprocess.run(
                ["git", "-C", str(cache_dir), "fetch", "--depth", "1", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if fetch.returncode != 0:
                message = (fetch.stderr or fetch.stdout or "Failed to refresh wallpaper source.").strip()
                return False, message, None
            reset = subprocess.run(
                ["git", "-C", str(cache_dir), "reset", "--hard", "FETCH_HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if reset.returncode != 0:
                message = (reset.stderr or reset.stdout or "Failed to update wallpaper source.").strip()
                return False, message, None
        else:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(cache_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            if clone.returncode != 0:
                message = (clone.stderr or clone.stdout or "Failed to clone wallpaper source.").strip()
                return False, message, None
    except Exception as exc:
        return False, str(exc), None

    source_dirs = wallpaper_source_directories(source_key, cache_dir)
    candidates: list[Path] = []
    source_labels: list[str] = []
    for source_dir in source_dirs:
        if not source_dir.exists():
            continue
        discovered = recursive_wallpaper_candidates(source_dir)
        if not discovered:
            continue
        candidates.extend(discovered)
        source_labels.append(str(source_dir))
    if not candidates:
        candidates = [
            path for path in cache_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
    if not candidates:
        return False, f"{preset['label']} does not currently expose wallpaper images in the expected paths.", None

    shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    seen_hashes: set[str] = set()
    for index, source in enumerate(sorted(candidates), start=1):
        digest = file_sha1(source)
        if digest and digest in seen_hashes:
            continue
        if digest:
            seen_hashes.add(digest)
        target = target_dir / f"{copied + 1:03d}-{source.name}"
        try:
            shutil.copy2(source, target)
            copied += 1
        except OSError:
            continue

    if copied == 0:
        return False, f"Hanauta could not copy any images from {preset['label']}.", None

    source_summary = ", ".join(source_labels[:2])
    if len(source_labels) > 2:
        source_summary += f", +{len(source_labels) - 2} more"
    if source_summary:
        return True, f"Synced {copied} image(s) from {preset['label']} using {source_summary}.", target_dir
    return True, f"Synced {copied} image(s) from {preset['label']}.", target_dir


class WallpaperSourceSyncWorker(QThread):
    finished_sync = pyqtSignal(str, bool, str, object)

    def __init__(self, source_key: str) -> None:
        super().__init__()
        self.source_key = source_key

    def run(self) -> None:
        ok, message, folder = sync_wallpaper_source_preset(self.source_key)
        self.finished_sync.emit(self.source_key, ok, message, folder)


def sanitize_output_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def draw_wallpaper_mode(painter: QPainter, source: QImage, width: int, height: int, mode: str) -> None:
    if source.isNull() or width <= 0 or height <= 0:
        return
    src_w = source.width()
    src_h = source.height()
    if src_w <= 0 or src_h <= 0:
        return

    if mode == "stretch":
        painter.drawImage(QRect(0, 0, width, height), source)
        return

    if mode == "tile":
        scaled = source
        if src_w > width or src_h > height:
            scaled = source.scaled(
                min(src_w, width),
                min(src_h, height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        for x in range(0, width, max(1, scaled.width())):
            for y in range(0, height, max(1, scaled.height())):
                painter.drawImage(x, y, scaled)
        return

    if mode == "center":
        x = (width - src_w) // 2
        y = (height - src_h) // 2
        painter.drawImage(x, y, source)
        return

    aspect_mode = (
        Qt.AspectRatioMode.KeepAspectRatio
        if mode == "fit"
        else Qt.AspectRatioMode.KeepAspectRatioByExpanding
    )
    scaled = source.scaled(width, height, aspect_mode, Qt.TransformationMode.SmoothTransformation)
    x = (width - scaled.width()) // 2
    y = (height - scaled.height()) // 2
    painter.drawImage(x, y, scaled)


def rounded_pixmap(path: Path, width: int, height: int, radius: int) -> QPixmap:
    source = QPixmap(str(path))
    if source.isNull():
        fallback = QPixmap(width, height)
        fallback.fill(QColor("#241d2b"))
        return fallback
    scaled = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    target = QPixmap(width, height)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return target


class IconLabel(QLabel):
    def __init__(self, glyph: str, font_family: str, size: int, color: str) -> None:
        super().__init__(glyph)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont(font_family, pointSize=size))
        self.setStyleSheet(f"color: {color}; background: transparent;")


class NavPillButton(QPushButton):
    def __init__(self, glyph: str, text: str, icon_font: str, text_font: str) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("navPill")
        self._compact = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.icon_label = QLabel(glyph)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 17))
        self.icon_label.setProperty("iconRole", True)
        self.icon_label.setFixedWidth(22)

        self.text_label = QLabel(text)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setWordWrap(False)
        self.text_label.setFont(QFont(text_font, 9))
        self.text_label.setStyleSheet("color: #FFFFFF; background: transparent;")

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignVCenter)

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        self.text_label.setVisible(not self._compact)
        self.setProperty("compact", self._compact)
        self.style().unpolish(self)
        self.style().polish(self)


class SegmentedChip(QPushButton):
    def __init__(self, text: str, checked: bool = False) -> None:
        super().__init__(text)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(30)
        self.setObjectName("segmentedChip")


class ThemeModeCard(QPushButton):
    def __init__(self, icon_text: str, title: str, icon_font: str, ui_font: str) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("themeModeCard")
        self.setMinimumSize(112, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(icon_font, 18))
        icon.setProperty("iconRole", True)
        icon.setStyleSheet("color: #FFFFFF; background: transparent;")

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont(ui_font, 10))
        label.setStyleSheet("color: #FFFFFF; background: transparent;")

        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addStretch(1)


class SwitchButton(QPushButton):
    toggledValue = pyqtSignal(bool)

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(50, 28)
        self.clicked.connect(self._emit_toggled)
        self._apply_state()

    def _emit_toggled(self) -> None:
        self._apply_state()
        self.toggledValue.emit(self.isChecked())

    def _apply_state(self) -> None:
        track = "#D7C2DC" if self.isChecked() else "rgba(255,255,255,0.18)"
        knob_x = 24 if self.isChecked() else 4
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {track};
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 14px;
            }}
            QPushButton::after {{
                content: '';
            }}
            """
        )
        self._knob_x = knob_x
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#251E2D" if self.isChecked() else "#F6ECFA"))
        painter.drawEllipse(self._knob_x, 3, 22, 22)
        painter.end()


class PreviewCard(QFrame):
    def __init__(self, wallpaper_path: Path, ui_font: str, display_font: str) -> None:
        super().__init__()
        self._ui_font = ui_font
        self._display_font = display_font
        self.setObjectName("previewCard")
        self.setMinimumHeight(214)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.wallpaper_label = QLabel()
        self.wallpaper_label.setScaledContents(False)
        self.wallpaper_label.setPixmap(rounded_pixmap(wallpaper_path, 430, 214, 18))
        self.wallpaper_label.setFixedHeight(214)
        self.wallpaper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay = QWidget(self.wallpaper_label)
        overlay.setGeometry(0, 0, 430, 214)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        ambient = QLabel(overlay)
        ambient.setGeometry(0, 0, 430, 214)
        ambient.setStyleSheet(
            """
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(31,22,38,0.14),
                stop:0.55 rgba(31,22,38,0.55),
                stop:1 rgba(24,17,31,0.84)
            );
            border-radius: 18px;
            """
        )

        chip = QLabel("Ambient preview", overlay)
        chip.move(14, 14)
        chip.setStyleSheet(
            f"""
            background: rgba(255,255,255,0.14);
            color: #F5EAF7;
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 10px;
            padding: 4px 8px;
            font-family: "{ui_font}";
            font-size: 10px;
            """
        )
        chip.adjustSize()

        title = QLabel("Wallpaper & Colors", overlay)
        title.move(14, 162)
        title.setFont(QFont(display_font, 16))
        title.setStyleSheet("color: #F8EEF7; background: transparent;")
        title.adjustSize()

        subtitle = QLabel("Expressive surfaces, soft contrast, and subtle translucency.", overlay)
        subtitle.move(14, 186)
        subtitle.setFont(QFont(ui_font, 9))
        subtitle.setStyleSheet("color: rgba(248,238,247,0.75); background: transparent;")
        subtitle.adjustSize()

        layout.addWidget(self.wallpaper_label)

    def update_wallpaper(self, wallpaper_path: Path) -> None:
        self.wallpaper_label.setPixmap(rounded_pixmap(wallpaper_path, 430, 214, 18))


class ActionCard(QPushButton):
    def __init__(self, icon_text: str, title: str, detail: str, icon_font: str, ui_font: str) -> None:
        super().__init__()
        self._icon_font = icon_font
        self._ui_font = ui_font
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("actionCard")
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("actionIconWrap")
        icon_wrap.setFixedSize(32, 32)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 15))
        self.icon_label.setProperty("iconRole", True)
        icon_layout.addWidget(self.icon_label)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(ui_font, 9, QFont.Weight.DemiBold))
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(QFont(ui_font, 8))
        self.detail_label.setStyleSheet("color: rgba(255,255,255,0.82); background: transparent;")

        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.detail_label)

        layout.addWidget(icon_wrap)
        layout.addLayout(text_wrap, 1)

    def set_content(self, icon_text: str, title: str, detail: str) -> None:
        self.icon_label.setText(icon_text)
        self.title_label.setText(title)
        self.detail_label.setText(detail)


class SettingsRow(QFrame):
    def __init__(self, icon_text: str, title: str, detail: str, icon_font: str, ui_font: str, trailing: QWidget) -> None:
        super().__init__()
        self.setObjectName("settingsRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("rowIconWrap")
        icon_wrap.setFixedSize(28, 28)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont(icon_font, 14))
        icon.setProperty("iconRole", True)
        icon_layout.addWidget(icon)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        title_label = QLabel(title)
        title_label.setFont(QFont(ui_font, 9))
        title_label.setStyleSheet("color: #FFFFFF; background: transparent;")

        detail_label = QLabel(detail)
        detail_label.setFont(QFont(ui_font, 8))
        detail_label.setStyleSheet("color: rgba(255,255,255,0.78); background: transparent;")

        text_wrap.addWidget(title_label)
        text_wrap.addWidget(detail_label)

        layout.addWidget(icon_wrap)
        layout.addLayout(text_wrap, 1)
        layout.addWidget(trailing, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class ExpandableServiceSection(QFrame):
    def __init__(
        self,
        key: str,
        title: str,
        detail: str,
        icon_text: str,
        icon_font: str,
        ui_font: str,
        content: QWidget,
        enabled: bool,
        on_toggle_enabled,
    ) -> None:
        super().__init__()
        self.key = key
        self.icon_font = icon_font
        self.ui_font = ui_font
        self._expanded = False
        self._content = content
        self.setObjectName("serviceSection")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.header_button = QPushButton()
        self.header_button.setObjectName("serviceHeaderButton")
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.setMinimumHeight(84)
        self.header_button.clicked.connect(self.toggle_expanded)
        header = QHBoxLayout(self.header_button)
        header.setContentsMargins(14, 14, 14, 14)
        header.setSpacing(12)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("rowIconWrap")
        icon_wrap.setFixedSize(32, 32)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont(icon_font, 16))
        self.icon_label.setProperty("iconRole", True)
        icon_layout.addWidget(self.icon_label)

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(5)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont(ui_font, 12, QFont.Weight.DemiBold))
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.detail_label = QLabel(detail)
        self.detail_label.setWordWrap(True)
        self.detail_label.setFont(QFont(ui_font, 9))
        self.detail_label.setStyleSheet("color: rgba(255,255,255,0.80); background: transparent;")
        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.detail_label)

        trailing = QHBoxLayout()
        trailing.setContentsMargins(0, 0, 0, 0)
        trailing.setSpacing(8)
        self.enabled_switch = SwitchButton(enabled)
        self.enabled_switch.toggledValue.connect(on_toggle_enabled)
        self.chevron = QLabel(material_icon("expand_more"))
        self.chevron.setObjectName("serviceChevron")
        self.chevron.setFont(QFont(icon_font, 18))
        self.chevron.setProperty("iconRole", True)
        trailing.addWidget(self.enabled_switch)
        trailing.addWidget(self.chevron)

        header.addWidget(icon_wrap)
        header.addLayout(text_wrap, 1)
        header.addLayout(trailing)

        self._content.setVisible(False)
        layout.addWidget(self.header_button)
        layout.addWidget(self._content)
        self.set_enabled(enabled)

    def toggle_expanded(self) -> None:
        if not self.enabled_switch.isChecked():
            return
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded and self.enabled_switch.isChecked()
        self._content.setVisible(self._expanded)
        self.chevron.setText(material_icon("expand_more"))
        self.chevron.setStyleSheet(
            "color: #F2E7F4; background: transparent;"
            + ("transform: rotate(180deg);" if self._expanded else "")
        )
        self.setProperty("expanded", self._expanded)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_enabled(self, enabled: bool) -> None:
        self.header_button.setEnabled(True)
        self.setProperty("serviceEnabled", enabled)
        self.header_button.setProperty("serviceEnabled", enabled)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if not enabled:
            self.set_expanded(False)
        self.style().unpolish(self)
        self.style().polish(self)


class SettingsWindow(QWidget):
    def __init__(self, initial_page: str = "appearance", initial_service_section: str = "") -> None:
        super().__init__()
        self.fonts = load_app_fonts()
        self.ui_font = detect_font(
            "Rubik",
            self.fonts.get("ui_sans_medium", ""),
            self.fonts.get("ui_sans", ""),
            "Google Sans",
            "Inter",
            "Noto Sans",
        )
        self.display_font = detect_font(
            "Rubik",
            self.fonts.get("ui_display_medium", ""),
            self.fonts.get("ui_display", ""),
            "Google Sans Display",
            self.ui_font,
        )
        self.icon_font = detect_font(
            self.fonts.get("material_icons", ""),
            self.fonts.get("material_icons_outlined", ""),
            "Material Icons",
        )

        self.settings_state = load_settings_state()
        self._weather_city_map: dict[str, WeatherCity] = {}
        self._selected_weather_city: WeatherCity | None = configured_city()
        self._weather_search_timer = QTimer(self)
        self._weather_search_timer.setSingleShot(True)
        self._weather_search_timer.timeout.connect(self._perform_weather_city_search)
        if not PYQT_THEME_FILE.exists() and not self.settings_state["appearance"].get("use_matugen_palette", False):
            write_default_pyqt_palette(use_matugen=False)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.current_accent = accent_palette(self.settings_state["appearance"].get("accent", "orchid"))
        self._refresh_current_accent()
        self.initial_page = initial_page
        self.initial_service_section = initial_service_section
        self._window_animation: QParallelAnimationGroup | None = None
        self._wallpaper_sync_worker: WallpaperSourceSyncWorker | None = None
        self._sidebar_collapsed = False
        self._slideshow_timer = QTimer(self)
        self._slideshow_timer.timeout.connect(self._advance_slideshow)
        self._slideshow_index = 0
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self.display_state = parse_xrandr_state()
        self.display_controls: dict[str, dict[str, QWidget]] = {}
        self.picom_state = parse_picom_settings(read_picom_text())
        self.wallpaper = self._pick_wallpaper()
        self.setWindowTitle("Hanauta Settings")
        self.setObjectName("settingsWindow")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1180, 720)
        self.setWindowOpacity(0.0)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(8, 5, 10, 150))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        shell = QFrame()
        shell.setObjectName("shell")
        outer.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        shell_layout.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(10)

        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_scroll_body(), 1)

        shell_layout.addLayout(body, 1)

        self._apply_styles()
        self._sync_wallpaper_controls()
        self._sync_accent_controls()
        self._refresh_system_overview()
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)
        self._slideshow_timer.setInterval(max(5, int(self.settings_state["appearance"].get("slideshow_interval", 30))) * 1000)
        if self.settings_state["appearance"].get("slideshow_enabled"):
            self._slideshow_timer.start()
        self._show_page(self.initial_page)

    def _pick_wallpaper(self) -> Path:
        configured = Path(self.settings_state["appearance"].get("wallpaper_path", "")).expanduser()
        if configured.exists() and configured.is_file():
            return configured
        if CURRENT_WALLPAPER.exists():
            return CURRENT_WALLPAPER
        preferred = [
            WALLS_DIR / "ryan-3.png",
            WALLS_DIR / "ryan-4.png",
            WALLS_DIR / "ryan-8.png",
        ]
        for candidate in preferred:
            if candidate.exists():
                return candidate
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            matches = sorted(WALLS_DIR.glob(pattern))
            if matches:
                return matches[0]
        return WALLS_DIR

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("topHeader")
        header.setFixedHeight(54)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        lead_chip = QFrame()
        lead_chip.setObjectName("headerLeadChip")
        lead_layout = QHBoxLayout(lead_chip)
        lead_layout.setContentsMargins(10, 6, 10, 6)
        lead_layout.setSpacing(6)
        lead_icon = QLabel("♪")
        lead_icon.setProperty("iconRole", True)
        lead_icon.setObjectName("headerLeadIcon")
        lead_icon.setFont(QFont(self.icon_font, 14))
        lead_text = QLabel("hanauta")
        lead_text.setObjectName("headerLeadText")
        lead_text.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        lead_layout.addWidget(lead_icon)
        lead_layout.addWidget(lead_text)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(1)
        title = QLabel("Settings")
        title.setObjectName("headerTitle")
        title.setFont(QFont(self.display_font, 12))
        subtitle = QLabel("Wallpaper, accents, and shell behavior")
        subtitle.setObjectName("headerSubtitle")
        subtitle.setFont(QFont(self.ui_font, 8))
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        close_button = QPushButton(material_icon("close"))
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setFixedSize(32, 32)
        close_button.setFont(QFont(self.icon_font, 16))
        close_button.setProperty("iconButton", True)
        close_button.clicked.connect(self.close)

        layout.addWidget(lead_chip, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(title_wrap, 1)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return header

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(244)

        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        self.sidebar_title = QLabel("Settings")
        self.sidebar_title.setObjectName("sidebarTitle")
        self.sidebar_title.setFont(QFont(self.display_font, 12, QFont.Weight.DemiBold))

        self.sidebar_menu_button = QPushButton(material_icon("menu"))
        self.sidebar_menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_menu_button.setFixedSize(38, 36)
        self.sidebar_menu_button.setFont(QFont(self.icon_font, 16))
        self.sidebar_menu_button.setProperty("iconButton", True)
        self.sidebar_menu_button.clicked.connect(self._toggle_sidebar)

        top_row.addWidget(self.sidebar_title, 1)
        top_row.addWidget(self.sidebar_menu_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_row)

        nav_section = QFrame()
        nav_section.setObjectName("sidebarNavSection")
        nav_layout = QVBoxLayout(nav_section)
        nav_layout.setContentsMargins(6, 8, 6, 8)
        nav_layout.setSpacing(6)

        self.sidebar_section_label = QLabel("Workspace")
        self.sidebar_section_label.setObjectName("sidebarSectionLabel")
        self.sidebar_section_label.setFont(QFont(self.ui_font, 8, QFont.Weight.DemiBold))
        nav_layout.addWidget(self.sidebar_section_label)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, NavPillButton] = {}

        items = [
            ("overview", material_icon("grid_view"), "Overview", False),
            ("appearance", material_icon("palette"), "Looks", True),
            ("display", material_icon("desktop_windows"), "Display", False),
            ("region", material_icon("public"), "Region", False),
            ("bar", material_icon("crop_square"), "Bar", False),
            ("services", material_icon("settings"), "Services", False),
            ("picom", material_icon("shadow"), "Picom", False),
        ]

        for key, glyph, label, checked in items:
            button = NavPillButton(glyph, label, self.icon_font, self.ui_font)
            button.setChecked(checked)
            button.clicked.connect(lambda checked=False, current=key: self._show_page(current))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            nav_layout.addWidget(button)

        layout.addWidget(nav_section)
        layout.addStretch(1)
        return self.sidebar

    def _build_scroll_body(self) -> QWidget:
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_overview_page())
        self.page_stack.addWidget(self._build_appearance_page())
        self.page_stack.addWidget(self._build_display_page())
        self.page_stack.addWidget(self._build_region_page())
        self.page_stack.addWidget(self._build_bar_page())
        self.page_stack.addWidget(self._build_services_page())
        self.page_stack.addWidget(self._build_picom_page())
        self._show_page(self.initial_page)
        return self.page_stack

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        if hasattr(self, "sidebar"):
            self.sidebar.setFixedWidth(84 if self._sidebar_collapsed else 244)
        if hasattr(self, "sidebar_title"):
            self.sidebar_title.setVisible(not self._sidebar_collapsed)
        if hasattr(self, "sidebar_section_label"):
            self.sidebar_section_label.setVisible(not self._sidebar_collapsed)
        for button in getattr(self, "nav_buttons", {}).values():
            button.set_compact(self._sidebar_collapsed)

    def _scroll_page(self, *widgets: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("bodyScroll")

        content = QWidget()
        content.setObjectName("content")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(10)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return scroll

    def _build_overview_page(self) -> QWidget:
        return self._scroll_page(self._build_system_overview_card())

    def _build_appearance_page(self) -> QWidget:
        return self._scroll_page(self._build_wallpaper_colors_card())

    def _build_bar_page(self) -> QWidget:
        return self._scroll_page(self._build_bar_screen_card())

    def _build_region_page(self) -> QWidget:
        return self._scroll_page(self._build_region_card())

    def _build_services_page(self) -> QWidget:
        return self._scroll_page(self._build_services_card())

    def _build_display_page(self) -> QWidget:
        return self._scroll_page(self._build_display_card())

    def _build_picom_page(self) -> QWidget:
        return self._scroll_page(self._build_picom_card())

    def _show_page(self, key: str) -> None:
        order = {"overview": 0, "appearance": 1, "display": 2, "region": 3, "bar": 4, "services": 5, "picom": 6}
        resolved = key if key in order else "appearance"
        self.page_stack.setCurrentIndex(order[resolved])
        for button_key, button in getattr(self, "nav_buttons", {}).items():
            button.setChecked(button_key == resolved)
        if resolved == "services" and self.initial_service_section:
            QTimer.singleShot(0, lambda: self._focus_service_section(self.initial_service_section))

    def _build_system_overview_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("grid_view"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("System Overview")
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        title.setFont(QFont(self.display_font, 13))
        subtitle = QLabel("Quick info for this session and shell environment.")
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle.setFont(QFont(self.ui_font, 9))
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.system_overview_labels: dict[str, QLabel] = {}
        for index, key in enumerate(("Host", "Kernel", "Session", "Python", "Uptime", "Screen")):
            label = QLabel("...")
            label.setFont(QFont(self.ui_font, 10))
            label.setStyleSheet("color: #FFFFFF;")
            self.system_overview_labels[key] = label
            grid.addWidget(self._metric_card(key, label), index // 2, index % 2)
        layout.addLayout(grid)
        return card

    def _metric_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setFont(QFont(self.ui_font, 8))
        title_label.setStyleSheet("color: rgba(246,235,247,0.62);")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card

    def _build_wallpaper_colors_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("appearanceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon = IconLabel(material_icon("palette"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        icon.setObjectName("appearanceHeaderIcon")
        title = QLabel("Wallpaper & Colors")
        title.setObjectName("appearanceTitle")
        title.setFont(QFont(self.display_font, 13))
        subtitle = QLabel("Pick, import, and rotate wallpapers without disturbing Matugen theming.")
        subtitle.setObjectName("appearanceSubtitle")
        subtitle.setFont(QFont(self.ui_font, 9))

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)

        layout.addLayout(header)

        hero_wrap = QFrame()
        hero_wrap.setObjectName("appearanceHeroWrap")
        hero = QHBoxLayout(hero_wrap)
        hero.setContentsMargins(14, 14, 14, 14)
        hero.setSpacing(12)
        self.preview_card = PreviewCard(self.wallpaper, self.ui_font, self.display_font)
        hero.addWidget(self.preview_card, 11)

        actions_wrap = QFrame()
        actions_wrap.setObjectName("appearanceActionColumn")
        actions = QVBoxLayout(actions_wrap)
        actions.setContentsMargins(14, 14, 14, 14)
        actions.setSpacing(8)
        self.random_wall_button = ActionCard(material_icon("auto_awesome"), "Random Wallpaper", "Pick a random image from your slideshow folder", self.icon_font, self.ui_font)
        self.choose_picture_button = ActionCard(material_icon("photo_library"), "Choose picture", "Select and apply a wallpaper image", self.icon_font, self.ui_font)
        self.choose_folder_button = ActionCard(material_icon("folder_open"), "Choose folder", "Use a folder as a slideshow source", self.icon_font, self.ui_font)
        self.slideshow_button = ActionCard(material_icon("image"), "Start slideshow", "Rotate wallpapers from the selected folder", self.icon_font, self.ui_font)
        self.sync_caelestia_button = ActionCard(material_icon("photo_library"), "Import Caelestia wallpapers", "Scan Caelestia wallpaper folders and copy every discovered image into Hanauta", self.icon_font, self.ui_font)
        self.sync_end4_button = ActionCard(material_icon("image"), "Import End-4 wallpapers", "Scan End-4 wallpaper folders, including local downloads, and copy every discovered image into Hanauta", self.icon_font, self.ui_font)
        self.random_wall_button.clicked.connect(self._apply_random_wallpaper)
        self.choose_picture_button.clicked.connect(self._choose_wallpaper_file)
        self.choose_folder_button.clicked.connect(self._choose_wallpaper_folder)
        self.slideshow_button.clicked.connect(self._toggle_slideshow)
        self.sync_caelestia_button.clicked.connect(lambda: self._sync_wallpaper_source("caelestia"))
        self.sync_end4_button.clicked.connect(lambda: self._sync_wallpaper_source("end4"))
        actions.addWidget(self.random_wall_button)
        actions.addWidget(self.choose_picture_button)
        actions.addWidget(self.choose_folder_button)
        actions.addWidget(self.slideshow_button)
        actions.addWidget(self.sync_caelestia_button)
        actions.addWidget(self.sync_end4_button)

        mode_heading = QLabel("Theme mode")
        mode_heading.setObjectName("appearanceSectionLabel")
        mode_heading.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        actions.addWidget(mode_heading)

        modes = QHBoxLayout()
        modes.setSpacing(8)
        light = ThemeModeCard(material_icon("light_mode"), "Light", self.icon_font, self.ui_font)
        dark = ThemeModeCard(material_icon("dark_mode"), "Dark", self.icon_font, self.ui_font)
        self.theme_buttons = {"light": light, "dark": dark}
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(light)
        self.mode_group.addButton(dark)
        light.clicked.connect(lambda: self._set_theme_mode("light"))
        dark.clicked.connect(lambda: self._set_theme_mode("dark"))
        modes.addWidget(light)
        modes.addWidget(dark)

        actions.addLayout(modes)
        actions.addStretch(1)
        hero.addWidget(actions_wrap, 8)
        layout.addWidget(hero_wrap)

        chips_frame = QFrame()
        chips_frame.setObjectName("appearanceAccentFrame")
        chips_outer = QVBoxLayout(chips_frame)
        chips_outer.setContentsMargins(14, 14, 14, 14)
        chips_outer.setSpacing(10)

        chips_heading = QLabel("Accent palette")
        chips_heading.setObjectName("appearanceSectionLabel")
        chips_heading.setFont(QFont(self.ui_font, 9, QFont.Weight.DemiBold))
        chips_outer.addWidget(chips_heading)

        chips = QWidget()
        chips_layout = QGridLayout(chips)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setHorizontalSpacing(8)
        chips_layout.setVerticalSpacing(8)

        labels = [
            "Auto",
            "Orchid",
            "Mint",
            "Sunset",
        ]
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.accent_chips: dict[str, SegmentedChip] = {}
        for index, label in enumerate(labels):
            chip = SegmentedChip(label, checked=False)
            self.chip_group.addButton(chip)
            key = label.lower()
            self.accent_chips[key] = chip
            chip.clicked.connect(lambda checked=False, current=key: self._set_accent(current))
            chips_layout.addWidget(chip, index // 6, index % 6)
        chips_outer.addWidget(chips)
        layout.addWidget(chips_frame)

        self.appearance_status = QLabel(
            "Built-in wallpaper import can pull from your Caelestia and End-4 wallpaper folders, including nested downloads."
        )
        self.appearance_status.setObjectName("settingsStatus")
        self.appearance_status.setFont(QFont(self.ui_font, 9))
        layout.addWidget(self.appearance_status)
        self.wallpaper_sync_progress = QProgressBar()
        self.wallpaper_sync_progress.setObjectName("settingsProgressBar")
        self.wallpaper_sync_progress.setRange(0, 0)
        self.wallpaper_sync_progress.setTextVisible(False)
        self.wallpaper_sync_progress.hide()
        layout.addWidget(self.wallpaper_sync_progress)

        self.slideshow_interval = QSlider(Qt.Orientation.Horizontal)
        self.slideshow_interval.setRange(5, 120)
        self.slideshow_interval.setValue(int(self.settings_state["appearance"].get("slideshow_interval", 30)))
        self.slideshow_interval.setFixedWidth(164)
        self.slideshow_interval.valueChanged.connect(self._set_slideshow_interval)

        transparency = SettingsRow(
            material_icon("opacity"),
            "Transparency",
            "Keep glass surfaces active across the shell.",
            self.icon_font,
            self.ui_font,
            self._make_transparency_switch(),
        )
        interval = SettingsRow(
            material_icon("image"),
            "Slideshow interval",
            "Set how often folder slideshow rotates the wallpaper.",
            self.icon_font,
            self.ui_font,
            self.slideshow_interval,
        )
        matugen_button = QPushButton("Refresh palette")
        matugen_button.setObjectName("secondaryButton")
        matugen_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        matugen_button.clicked.connect(lambda: self._apply_matugen_palette(force=True))
        matugen = SettingsRow(
            material_icon("auto_awesome"),
            "Wallpaper-driven colors",
            "Use Matugen to generate a shared palette file for the dock and bar.",
            self.icon_font,
            self.ui_font,
            matugen_button,
        )
        matugen_toggle = SettingsRow(
            material_icon("palette"),
            "Enable Matugen theming",
            "When enabled, wallpaper changes regenerate the dock and bar palette.",
            self.icon_font,
            self.ui_font,
            self._make_matugen_switch(),
        )
        layout.addWidget(transparency)
        layout.addWidget(interval)
        layout.addWidget(matugen_toggle)
        layout.addWidget(matugen)
        return card

    def _build_display_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("desktop_windows"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Displays")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel("Primary monitor, extend or duplicate mode, resolution, refresh rate, and rotation.")
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_button.clicked.connect(self._refresh_display_state)
        apply_button = QPushButton("Apply displays")
        apply_button.setObjectName("primaryButton")
        apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_button.clicked.connect(self._apply_display_settings)
        actions.addWidget(refresh_button)
        actions.addWidget(apply_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.display_status = QLabel("")
        self.display_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.display_status.setWordWrap(True)
        layout.addWidget(self.display_status)

        if not self.display_state:
            self.display_status.setText("No displays detected through xrandr.")
            return card

        connected_count = len(self.display_state)
        if connected_count > 1:
            layout.addWidget(self._build_display_global_card())
        else:
            self.display_status.setText("Single display detected. Primary and mirror controls are hidden.")

        self.display_outputs_container = QVBoxLayout()
        self.display_outputs_container.setContentsMargins(0, 0, 0, 0)
        self.display_outputs_container.setSpacing(10)
        layout.addLayout(self.display_outputs_container)
        self._rebuild_display_output_cards()
        return card

    def _build_display_global_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("settingsRow")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Multi-monitor layout")
        title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
        title.setStyleSheet("color: #FFFFFF;")
        detail = QLabel("Choose the primary display and whether active outputs extend left-to-right or mirror the primary.")
        detail.setFont(QFont(self.ui_font, 8))
        detail.setStyleSheet("color: rgba(246,235,247,0.72);")
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)

        row = QHBoxLayout()
        row.setSpacing(10)
        primary_label = QLabel("Primary")
        primary_label.setFont(QFont(self.ui_font, 9))
        primary_label.setStyleSheet("color: rgba(246,235,247,0.78);")
        self.primary_display_combo = QComboBox()
        self.primary_display_combo.setObjectName("settingsCombo")
        for display in self.display_state:
            self.primary_display_combo.addItem(display["name"])
        primary_name = next((display["name"] for display in self.display_state if display.get("primary")), self.display_state[0]["name"])
        self.primary_display_combo.setCurrentText(primary_name)
        row.addWidget(primary_label)
        row.addWidget(self.primary_display_combo, 1)
        layout.addLayout(row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.display_layout_buttons: dict[str, SegmentedChip] = {}
        self.display_layout_group = QButtonGroup(self)
        self.display_layout_group.setExclusive(True)
        for key, label in (("extend", "Extend"), ("duplicate", "Duplicate")):
            chip = SegmentedChip(label, checked=(key == "extend"))
            chip.clicked.connect(lambda checked=False, current=key: self._set_display_layout_mode(current))
            self.display_layout_group.addButton(chip)
            self.display_layout_buttons[key] = chip
            mode_row.addWidget(chip)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)
        self.display_layout_mode = "extend"
        self._set_display_layout_mode("extend")
        return card

    def _rebuild_display_output_cards(self) -> None:
        while self.display_outputs_container.count():
            item = self.display_outputs_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.display_controls = {}
        multi = len(self.display_state) > 1
        for display in self.display_state:
            card = QFrame()
            card.setObjectName("settingsRow")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            title_row = QHBoxLayout()
            title = QLabel(display["name"])
            title.setFont(QFont(self.ui_font, 10, QFont.Weight.DemiBold))
            title.setStyleSheet("color: #FFFFFF;")
            desc_bits = []
            if display.get("primary"):
                desc_bits.append("Primary")
            desc_bits.append("Active" if display.get("enabled") else "Connected but inactive")
            subtitle = QLabel(" • ".join(desc_bits))
            subtitle.setFont(QFont(self.ui_font, 8))
            subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
            title_wrap = QVBoxLayout()
            title_wrap.setContentsMargins(0, 0, 0, 0)
            title_wrap.setSpacing(2)
            title_wrap.addWidget(title)
            title_wrap.addWidget(subtitle)
            title_row.addLayout(title_wrap)
            title_row.addStretch(1)
            layout.addLayout(title_row)

            control_grid = QGridLayout()
            control_grid.setContentsMargins(0, 0, 0, 0)
            control_grid.setHorizontalSpacing(10)
            control_grid.setVerticalSpacing(10)

            enabled_switch = SwitchButton(bool(display.get("enabled", True)))
            enabled_switch.setEnabled(multi)

            resolution_combo = QComboBox()
            resolution_combo.setObjectName("settingsCombo")
            for mode in display.get("modes", []):
                resolution_combo.addItem(mode)
            if display.get("current_mode"):
                resolution_combo.setCurrentText(display["current_mode"])

            refresh_combo = QComboBox()
            refresh_combo.setObjectName("settingsCombo")

            orientation_combo = QComboBox()
            orientation_combo.setObjectName("settingsCombo")
            for option in ("normal", "left", "right", "inverted"):
                orientation_combo.addItem(option)
            orientation_combo.setCurrentText(display.get("orientation", "normal"))

            wallpaper_combo = QComboBox()
            wallpaper_combo.setObjectName("settingsCombo")
            wallpaper_combo.blockSignals(True)
            for option in ("fill", "fit", "center", "stretch", "tile"):
                wallpaper_combo.addItem(option.title(), option)
            saved_mode = str(
                self.settings_state["appearance"]
                .get("wallpaper_fit_modes", {})
                .get(display["name"], "fill")
            )
            wallpaper_combo.setCurrentText(saved_mode.title())
            wallpaper_combo.blockSignals(False)
            wallpaper_combo.currentTextChanged.connect(
                lambda _text, current=display["name"], combo=wallpaper_combo: self._set_display_wallpaper_mode(
                    current,
                    str(combo.currentData() or combo.currentText().lower()),
                )
            )

            resolution_combo.currentTextChanged.connect(
                lambda mode, current=display["name"]: self._sync_refresh_rates_for_output(current, mode)
            )
            self.display_controls[display["name"]] = {
                "enabled": enabled_switch,
                "resolution": resolution_combo,
                "refresh": refresh_combo,
                "orientation": orientation_combo,
                "wallpaper": wallpaper_combo,
            }
            self._sync_refresh_rates_for_output(display["name"], resolution_combo.currentText())

            control_grid.addWidget(self._settings_labeled_field("Enabled", enabled_switch), 0, 0)
            control_grid.addWidget(self._settings_labeled_field("Resolution", resolution_combo), 0, 1)
            control_grid.addWidget(self._settings_labeled_field("Refresh", refresh_combo), 1, 0)
            control_grid.addWidget(self._settings_labeled_field("Orientation", orientation_combo), 1, 1)
            control_grid.addWidget(self._settings_labeled_field("Wallpaper", wallpaper_combo), 2, 0, 1, 2)
            layout.addLayout(control_grid)
            self.display_outputs_container.addWidget(card)

    def _settings_labeled_field(self, label_text: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setFont(QFont(self.ui_font, 8))
        label.setStyleSheet("color: rgba(246,235,247,0.62);")
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrap

    def _sync_refresh_rates_for_output(self, output_name: str, mode: str) -> None:
        controls = self.display_controls.get(output_name, {})
        refresh_combo = controls.get("refresh")
        if not isinstance(refresh_combo, QComboBox):
            return
        display = next((item for item in self.display_state if item["name"] == output_name), None)
        if display is None:
            return
        refresh_combo.blockSignals(True)
        refresh_combo.clear()
        rates = list(display.get("refresh_rates", {}).get(mode, []))
        if not rates:
            refresh_combo.addItem("Auto")
        else:
            refresh_combo.addItem("Auto")
            for rate in rates:
                refresh_combo.addItem(rate)
            current_refresh = str(display.get("current_refresh", ""))
            if current_refresh and current_refresh in rates:
                refresh_combo.setCurrentText(current_refresh)
        refresh_combo.blockSignals(False)

    def _set_display_layout_mode(self, mode: str) -> None:
        self.display_layout_mode = mode
        for key, chip in getattr(self, "display_layout_buttons", {}).items():
            chip.setChecked(key == mode)

    def _set_display_wallpaper_mode(self, output_name: str, mode: str) -> None:
        fit_modes = self.settings_state["appearance"].setdefault("wallpaper_fit_modes", {})
        fit_modes[output_name] = mode
        save_settings_state(self.settings_state)
        self._apply_current_wallpaper_layout()

    def _refresh_display_state(self) -> None:
        self.display_state = parse_xrandr_state()
        self.display_status.setText("Display state refreshed from xrandr." if self.display_state else "No displays detected through xrandr.")
        if hasattr(self, "primary_display_combo"):
            self.primary_display_combo.clear()
            for display in self.display_state:
                self.primary_display_combo.addItem(display["name"])
            if self.display_state:
                saved_primary = str(self.settings_state.get("display", {}).get("primary", ""))
                available_names = {display["name"] for display in self.display_state}
                if saved_primary in available_names:
                    primary_name = saved_primary
                else:
                    primary_name = next((display["name"] for display in self.display_state if display.get("primary")), self.display_state[0]["name"])
                self.primary_display_combo.setCurrentText(primary_name)
        saved_layout = str(self.settings_state.get("display", {}).get("layout_mode", "extend"))
        if saved_layout in {"extend", "duplicate"}:
            self._set_display_layout_mode(saved_layout)
        self._rebuild_display_output_cards()

    def _collect_display_form_state(self) -> list[dict]:
        collected: list[dict] = []
        saved_outputs = {
            str(item.get("name", "")): item
            for item in self.settings_state.get("display", {}).get("outputs", [])
            if isinstance(item, dict)
        }
        for display in self.display_state:
            controls = self.display_controls.get(display["name"], {})
            enabled_widget = controls.get("enabled")
            resolution_widget = controls.get("resolution")
            refresh_widget = controls.get("refresh")
            orientation_widget = controls.get("orientation")
            saved = saved_outputs.get(display["name"], {})
            collected.append(
                {
                    "name": display["name"],
                    "enabled": bool(enabled_widget.isChecked()) if isinstance(enabled_widget, SwitchButton) else bool(saved.get("enabled", display.get("enabled"))),
                    "resolution": resolution_widget.currentText() if isinstance(resolution_widget, QComboBox) else str(saved.get("resolution", display.get("current_mode", ""))),
                    "refresh": refresh_widget.currentText() if isinstance(refresh_widget, QComboBox) else str(saved.get("refresh", "Auto")),
                    "orientation": orientation_widget.currentText() if isinstance(orientation_widget, QComboBox) else str(saved.get("orientation", display.get("orientation", "normal"))),
                    "modes": list(display.get("modes", [])),
                }
            )
        return collected

    def _apply_display_settings(self) -> None:
        displays = self._collect_display_form_state()
        enabled = [display for display in displays if display["enabled"]]
        if not enabled:
            self.display_status.setText("At least one display must stay enabled.")
            return

        primary_name = enabled[0]["name"]
        if len(self.display_state) > 1 and hasattr(self, "primary_display_combo"):
            primary_name = self.primary_display_combo.currentText() or enabled[0]["name"]
            if primary_name not in {display["name"] for display in enabled}:
                primary_name = enabled[0]["name"]

        if self.display_layout_mode == "duplicate" and len(enabled) > 1:
            common_modes = set(enabled[0]["modes"])
            for display in enabled[1:]:
                common_modes &= set(display["modes"])
            if not common_modes:
                self.display_status.setText("No shared resolution is available across enabled displays for duplicate mode.")
                return
            primary_display = next(display for display in enabled if display["name"] == primary_name)
            if primary_display["resolution"] not in common_modes:
                primary_display["resolution"] = sorted(common_modes, key=resolution_area, reverse=True)[0]
            for display in enabled:
                display["resolution"] = primary_display["resolution"]
                if display["name"] != primary_name:
                    display["refresh"] = "Auto"

        cmd = build_display_command(displays, primary_name, self.display_layout_mode)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            self.display_status.setText((result.stderr or result.stdout or "Failed to apply display settings.").strip())
            return
        self.settings_state["display"] = {
            "layout_mode": self.display_layout_mode,
            "primary": primary_name,
            "outputs": [
                {
                    "name": display["name"],
                    "enabled": bool(display["enabled"]),
                    "resolution": str(display["resolution"]),
                    "refresh": str(display["refresh"]),
                    "orientation": str(display["orientation"]),
                }
                for display in displays
            ],
        }
        save_settings_state(self.settings_state)
        self.display_status.setText("Display layout applied.")
        self._refresh_display_state()
        self._apply_current_wallpaper_layout()

    def _build_picom_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("shadow"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Picom")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        subtitle = QLabel("Core compositor behavior, shadows, opacity, and corners from picom.conf.")
        subtitle.setFont(QFont(self.ui_font, 9))
        subtitle.setStyleSheet("color: rgba(246,235,247,0.72);")
        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addWidget(icon)
        header.addLayout(title_wrap)
        header.addStretch(1)
        layout.addLayout(header)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        apply_button = QPushButton("Apply picom")
        apply_button.setObjectName("primaryButton")
        apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_button.clicked.connect(self._apply_picom_settings)
        restart_button = QPushButton("Restart picom")
        restart_button.setObjectName("secondaryButton")
        restart_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        restart_button.clicked.connect(self._restart_picom)
        reset_button = QPushButton("Reset defaults")
        reset_button.setObjectName("dangerButton")
        reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_button.clicked.connect(self._reset_picom_defaults)
        actions.addWidget(apply_button)
        actions.addWidget(restart_button)
        actions.addWidget(reset_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.picom_status = QLabel("")
        self.picom_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.picom_status.setWordWrap(True)
        layout.addWidget(self.picom_status)

        self.picom_backend_combo = QComboBox()
        self.picom_backend_combo.setObjectName("settingsCombo")
        self.picom_backend_combo.addItems(["glx", "xrender"])
        self.picom_backend_combo.setCurrentText(str(self.picom_state.get("backend", "glx")))

        self.picom_vsync_switch = SwitchButton(bool(self.picom_state.get("vsync", True)))
        self.picom_damage_switch = SwitchButton(bool(self.picom_state.get("use-damage", True)))
        self.picom_shadow_switch = SwitchButton(bool(self.picom_state.get("shadow", True)))
        self.picom_fading_switch = SwitchButton(bool(self.picom_state.get("fading", False)))
        self.picom_clip_switch = SwitchButton(bool(self.picom_state.get("transparent-clipping", False)))
        self.picom_rounded_switch = SwitchButton(bool(self.picom_state.get("detect-rounded-corners", True)))

        layout.addWidget(SettingsRow(material_icon("tune"), "Backend", "Choose the renderer used by picom.", self.icon_font, self.ui_font, self.picom_backend_combo))
        layout.addWidget(SettingsRow(material_icon("sync"), "VSync", "Reduce tearing by syncing frames.", self.icon_font, self.ui_font, self.picom_vsync_switch))
        layout.addWidget(SettingsRow(material_icon("widgets"), "Use damage", "Only redraw changed regions where possible.", self.icon_font, self.ui_font, self.picom_damage_switch))
        layout.addWidget(SettingsRow(material_icon("shadow"), "Shadows", "Enable shadow rendering around windows.", self.icon_font, self.ui_font, self.picom_shadow_switch))
        layout.addWidget(self._slider_settings_row("Shadow radius", "Blur radius for shadows.", 0, 60, int(self.picom_state.get("shadow-radius", 18)), material_icon("shadow"), "picom_shadow_radius"))
        layout.addWidget(self._slider_settings_row("Shadow opacity", "Overall shadow strength.", 0, 100, int(float(self.picom_state.get("shadow-opacity", 0.18)) * 100), material_icon("opacity"), "picom_shadow_opacity"))
        layout.addWidget(self._slider_settings_row("Shadow offset X", "Horizontal shadow offset.", -40, 40, int(self.picom_state.get("shadow-offset-x", -12)), material_icon("tune"), "picom_shadow_offset_x"))
        layout.addWidget(self._slider_settings_row("Shadow offset Y", "Vertical shadow offset.", -40, 40, int(self.picom_state.get("shadow-offset-y", -12)), material_icon("tune"), "picom_shadow_offset_y"))
        layout.addWidget(SettingsRow(material_icon("auto_awesome"), "Fading", "Fade transitions for mapped and unmapped windows.", self.icon_font, self.ui_font, self.picom_fading_switch))
        layout.addWidget(self._slider_settings_row("Active opacity", "Opacity for focused windows.", 50, 100, int(float(self.picom_state.get("active-opacity", 1.0)) * 100), material_icon("opacity"), "picom_active_opacity"))
        layout.addWidget(self._slider_settings_row("Inactive opacity", "Opacity for unfocused windows.", 50, 100, int(float(self.picom_state.get("inactive-opacity", 1.0)) * 100), material_icon("opacity"), "picom_inactive_opacity"))
        layout.addWidget(self._slider_settings_row("Corner radius", "Rounded corner radius in pixels.", 0, 40, int(self.picom_state.get("corner-radius", 18)), material_icon("flip"), "picom_corner_radius"))
        layout.addWidget(SettingsRow(material_icon("crop_square"), "Transparent clipping", "Clip transparent pixels before drawing.", self.icon_font, self.ui_font, self.picom_clip_switch))
        layout.addWidget(SettingsRow(material_icon("flip"), "Detect rounded corners", "Respect client-side rounded corners when available.", self.icon_font, self.ui_font, self.picom_rounded_switch))
        return card

    def _slider_settings_row(self, title: str, detail: str, minimum: int, maximum: int, value: int, icon: str, attr_prefix: str) -> QWidget:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setFixedWidth(180)
        label = QLabel(str(value))
        label.setFixedWidth(36)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("color: rgba(246,235,247,0.78);")
        slider.valueChanged.connect(lambda current, target=label: target.setText(str(current)))
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(slider)
        row.addWidget(label)
        setattr(self, f"{attr_prefix}_slider", slider)
        setattr(self, f"{attr_prefix}_label", label)
        return SettingsRow(icon, title, detail, self.icon_font, self.ui_font, wrap)

    def _build_bar_screen_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("dock_to_left"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Bar & screen")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        self.bar_launcher_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_launcher_offset_slider.setRange(-8, 8)
        self.bar_launcher_offset_slider.setValue(int(self.settings_state["bar"].get("launcher_offset", 0)))
        self.bar_launcher_offset_slider.setFixedWidth(164)
        self.bar_launcher_offset_slider.valueChanged.connect(self._set_bar_launcher_offset)

        self.bar_workspace_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_workspace_offset_slider.setRange(-8, 8)
        self.bar_workspace_offset_slider.setValue(int(self.settings_state["bar"].get("workspace_offset", 0)))
        self.bar_workspace_offset_slider.setFixedWidth(164)
        self.bar_workspace_offset_slider.valueChanged.connect(self._set_bar_workspace_offset)

        self.bar_datetime_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_datetime_offset_slider.setRange(-8, 8)
        self.bar_datetime_offset_slider.setValue(int(self.settings_state["bar"].get("datetime_offset", 0)))
        self.bar_datetime_offset_slider.setFixedWidth(164)
        self.bar_datetime_offset_slider.valueChanged.connect(self._set_bar_datetime_offset)

        self.bar_media_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_media_offset_slider.setRange(-8, 8)
        self.bar_media_offset_slider.setValue(int(self.settings_state["bar"].get("media_offset", 0)))
        self.bar_media_offset_slider.setFixedWidth(164)
        self.bar_media_offset_slider.valueChanged.connect(self._set_bar_media_offset)

        self.bar_status_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_status_offset_slider.setRange(-8, 8)
        self.bar_status_offset_slider.setValue(int(self.settings_state["bar"].get("status_offset", 0)))
        self.bar_status_offset_slider.setFixedWidth(164)
        self.bar_status_offset_slider.valueChanged.connect(self._set_bar_status_offset)

        self.bar_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_height_slider.setRange(32, 72)
        self.bar_height_slider.setValue(int(self.settings_state["bar"].get("bar_height", 40)))
        self.bar_height_slider.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.bar_height_slider.setInvertedAppearance(False)
        self.bar_height_slider.setInvertedControls(False)
        self.bar_height_slider.setFixedWidth(164)
        self.bar_height_slider.valueChanged.connect(self._set_bar_height)

        self.bar_chip_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_chip_radius_slider.setRange(0, 32)
        self.bar_chip_radius_slider.setValue(int(self.settings_state["bar"].get("chip_radius", 0)))
        self.bar_chip_radius_slider.setFixedWidth(164)
        self.bar_chip_radius_slider.valueChanged.connect(self._set_bar_chip_radius)

        self.bar_full_merge_switch = SwitchButton(bool(self.settings_state["bar"].get("merge_all_chips", False)))
        self.bar_full_merge_switch.toggledValue.connect(self._set_bar_merge_all_chips)

        self.bar_full_radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.bar_full_radius_slider.setRange(0, 32)
        self.bar_full_radius_slider.setValue(int(self.settings_state["bar"].get("full_bar_radius", 18)))
        self.bar_full_radius_slider.setFixedWidth(164)
        self.bar_full_radius_slider.valueChanged.connect(self._set_bar_full_radius)

        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Launcher / AI offset",
                "Move the AI icon and launcher block up or down without changing their internal alignment.",
                self.icon_font,
                self.ui_font,
                self.bar_launcher_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Workspace offset",
                "Move the workspace block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_workspace_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Date/time offset",
                "Move the clock and date block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_datetime_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Media offset",
                "Move the now playing block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_media_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Status offset",
                "Move the network, battery, tray, and power block up or down as a whole.",
                self.icon_font,
                self.ui_font,
                self.bar_status_offset_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("dock_to_left"),
                "Bar height",
                "Increase or reduce the overall bar height whether you use separate chips or the merged full bar.",
                self.icon_font,
                self.ui_font,
                self.bar_height_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Chip corner radius",
                "Adjust how square or rounded the bar chips should be.",
                self.icon_font,
                self.ui_font,
                self.bar_chip_radius_slider,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("dock_to_left"),
                "Merge chips into full bar",
                "Blend the separate chips into one continuous bar surface.",
                self.icon_font,
                self.ui_font,
                self.bar_full_merge_switch,
            )
        )
        layout.addWidget(
            SettingsRow(
                material_icon("flip"),
                "Full bar corner radius",
                "When full bar mode is enabled, choose how rounded the overall bar should be.",
                self.icon_font,
                self.ui_font,
                self.bar_full_radius_slider,
            )
        )
        return card

    def _build_region_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("public"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Region & locale")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        detected_locale = ""
        try:
            current_locale = pylocale.setlocale(pylocale.LC_TIME, None)
            if current_locale and current_locale.upper() != "C":
                detected_locale = current_locale
        except Exception:
            detected_locale = ""
        if not detected_locale:
            try:
                locale_pair = pylocale.getlocale()
            except Exception:
                locale_pair = (None, None)
            if locale_pair and locale_pair[0]:
                detected_locale = locale_pair[0]
                try:
                    encoding = pylocale.getencoding()
                except Exception:
                    encoding = ""
                if encoding and "." not in detected_locale:
                    detected_locale = f"{detected_locale}.{encoding}"
        self.region_locale_input = QLineEdit(self.settings_state["region"].get("locale_code", detected_locale))
        self.region_locale_input.setPlaceholderText(detected_locale or "en_US.UTF-8")
        layout.addWidget(
            SettingsRow(
                material_icon("language"),
                "Locale code",
                "Used by Hanauta for the locale badge and regional formatting preferences. Example: en_US.UTF-8 or pt_BR.UTF-8.",
                self.icon_font,
                self.ui_font,
                self.region_locale_input,
            )
        )

        self.region_24h_switch = SwitchButton(bool(self.settings_state["region"].get("use_24_hour", False)))
        self.region_24h_switch.toggledValue.connect(self._set_region_use_24_hour)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "24-hour clock",
                "Use 24-hour time in the bar instead of AM/PM.",
                self.icon_font,
                self.ui_font,
                self.region_24h_switch,
            )
        )

        self.region_date_style_combo = QComboBox()
        self.region_date_style_combo.setObjectName("settingsCombo")
        self.region_date_style_combo.addItem("US", "us")
        self.region_date_style_combo.addItem("ISO", "iso")
        self.region_date_style_combo.addItem("European", "eu")
        current_date_style = str(self.settings_state["region"].get("date_style", "us"))
        date_style_index = self.region_date_style_combo.findData(current_date_style)
        self.region_date_style_combo.setCurrentIndex(max(0, date_style_index))
        self.region_date_style_combo.currentIndexChanged.connect(self._set_region_date_style)
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Date style",
                "Controls how the bar renders the date label.",
                self.icon_font,
                self.ui_font,
                self.region_date_style_combo,
            )
        )

        self.region_temperature_combo = QComboBox()
        self.region_temperature_combo.setObjectName("settingsCombo")
        self.region_temperature_combo.addItem("Celsius", "c")
        self.region_temperature_combo.addItem("Fahrenheit", "f")
        current_temp_style = str(self.settings_state["region"].get("temperature_unit", "c"))
        temp_style_index = self.region_temperature_combo.findData(current_temp_style)
        self.region_temperature_combo.setCurrentIndex(max(0, temp_style_index))
        self.region_temperature_combo.currentIndexChanged.connect(self._set_region_temperature_unit)
        layout.addWidget(
            SettingsRow(
                material_icon("partly_cloudy_day"),
                "Temperature unit",
                "Used by Hanauta weather surfaces when a converted regional unit is needed.",
                self.icon_font,
                self.ui_font,
                self.region_temperature_combo,
            )
        )

        self.region_status = QLabel("Regional formatting is ready.")
        self.region_status.setWordWrap(True)
        self.region_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.region_status)

        save_button = QPushButton("Save region settings")
        save_button.setObjectName("primaryButton")
        save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_button.clicked.connect(self._save_region_settings)
        layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_services_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = IconLabel(material_icon("settings"), self.icon_font, 15, "#F4EAF7")
        icon.setFixedSize(22, 22)
        title = QLabel("Services")
        title.setFont(QFont(self.display_font, 13))
        title.setStyleSheet("color: rgba(246,235,247,0.72);")
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        self.service_sections: dict[str, ExpandableServiceSection] = {}
        self.service_display_switches: dict[str, SwitchButton] = {}
        for key, widget in (
            ("home_assistant", self._build_home_assistant_section()),
            ("vpn_control", self._build_vpn_service_section()),
            ("christian_widget", self._build_christian_service_section()),
            ("calendar_widget", self._build_calendar_service_section()),
            ("reminders_widget", self._build_reminders_service_section()),
            ("pomodoro_widget", self._build_pomodoro_service_section()),
            ("rss_widget", self._build_rss_service_section()),
            ("obs_widget", self._build_obs_service_section()),
            ("crypto_widget", self._build_crypto_service_section()),
            ("vps_widget", self._build_vps_service_section()),
            ("desktop_clock_widget", self._build_desktop_clock_service_section()),
            ("weather", self._build_weather_section()),
            ("ntfy", self._build_ntfy_section()),
        ):
            layout.addWidget(widget)
        return card

    def _focus_service_section(self, key: str) -> None:
        section = getattr(self, "service_sections", {}).get(key)
        if section is None:
            return
        if section.enabled_switch.isChecked():
            section.set_expanded(True)
            section.header_button.setFocus()
        self.initial_service_section = ""

    def _build_home_assistant_section(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self.ha_url_input = QLineEdit(self.settings_state["home_assistant"].get("url", ""))
        self.ha_url_input.setPlaceholderText("https://homeassistant.local:8123")
        self.ha_token_input = QLineEdit(self.settings_state["home_assistant"].get("token", ""))
        self.ha_token_input.setPlaceholderText("Long-lived access token")
        self.ha_token_input.setEchoMode(QLineEdit.EchoMode.Password)

        url_row = SettingsRow(material_icon("web_asset"), "Server URL", "Home Assistant base URL.", self.icon_font, self.ui_font, self.ha_url_input)
        token_row = SettingsRow(material_icon("bolt"), "Access token", "Used to fetch and pin entities.", self.icon_font, self.ui_font, self.ha_token_input)
        content_layout.addWidget(url_row)
        content_layout.addWidget(token_row)

        self.ha_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["home_assistant"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.ha_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("home_assistant", enabled)
        )
        self.service_display_switches["home_assistant"] = self.ha_display_switch
        content_layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Display the Home Assistant widget in the notification center overview.",
                self.icon_font,
                self.ui_font,
                self.ha_display_switch,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.ha_save_button = QPushButton("Save")
        self.ha_refresh_button = QPushButton("Fetch Entities")
        self.ha_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ha_refresh_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ha_save_button.clicked.connect(self._save_home_assistant_settings)
        self.ha_refresh_button.clicked.connect(self._refresh_home_assistant_entities)
        buttons.addWidget(self.ha_save_button)
        buttons.addWidget(self.ha_refresh_button)
        content_layout.addLayout(buttons)

        self.ha_status = QLabel("Home Assistant is idle.")
        self.ha_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        content_layout.addWidget(self.ha_status)

        self.ha_entity_scroll = QScrollArea()
        self.ha_entity_scroll.setWidgetResizable(True)
        self.ha_entity_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ha_entity_scroll.setObjectName("bodyScroll")
        self.ha_entity_container = QWidget()
        self.ha_entity_layout = QVBoxLayout(self.ha_entity_container)
        self.ha_entity_layout.setContentsMargins(0, 0, 0, 0)
        self.ha_entity_layout.setSpacing(8)
        self.ha_entity_scroll.setWidget(self.ha_entity_container)
        content_layout.addWidget(self.ha_entity_scroll, 1)

        self._rebuild_ha_entity_list()
        section = ExpandableServiceSection(
            "home_assistant",
            "Home Assistant",
            "Credentials, pinned entities, and notification center visibility.",
            material_icon("home"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("home_assistant"),
            lambda enabled: self._set_service_enabled("home_assistant", enabled),
        )
        self.service_sections["home_assistant"] = section
        return section

    def _build_vpn_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["vpn_control"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("vpn_control", enabled)
        )
        self.service_display_switches["vpn_control"] = display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a compact launcher card for the VPN control popup.",
                self.icon_font,
                self.ui_font,
                display_switch,
            )
        )
        reconnect_switch = SwitchButton(
            bool(
                self.settings_state["services"]["vpn_control"].get(
                    "reconnect_on_login",
                    False,
                )
            )
        )
        reconnect_switch.toggledValue.connect(
            lambda enabled: self._set_vpn_service_flag("reconnect_on_login", enabled)
        )
        self.vpn_reconnect_switch = reconnect_switch
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Reconnect on session start",
                "Bring the selected WireGuard tunnel back when this desktop session starts.",
                self.icon_font,
                self.ui_font,
                reconnect_switch,
            )
        )
        section = ExpandableServiceSection(
            "vpn_control",
            "VPN Control",
            "Enable the WireGuard popup, keep a preferred tunnel remembered, and optionally reopen it on session start.",
            material_icon("lock"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("vpn_control"),
            lambda enabled: self._set_service_enabled("vpn_control", enabled),
        )
        self.service_sections["vpn_control"] = section
        return section

    def _build_christian_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        display_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("christian_widget", enabled)
        )
        self.service_display_switches["christian_widget"] = display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Display a tinted Christian devotion launcher icon on the bar.",
                self.icon_font,
                self.ui_font,
                display_switch,
            )
        )
        next_devotion_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "next_devotion_notifications",
                    False,
                )
            )
        )
        next_devotion_switch.toggledValue.connect(
            lambda enabled: self._set_christian_service_flag("next_devotion_notifications", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Next devotion notifications",
                "Send a desktop notification when the next devotion time begins.",
                self.icon_font,
                self.ui_font,
                next_devotion_switch,
            )
        )
        hourly_verse_switch = SwitchButton(
            bool(
                self.settings_state["services"]["christian_widget"].get(
                    "hourly_verse_notifications",
                    False,
                )
            )
        )
        hourly_verse_switch.toggledValue.connect(
            lambda enabled: self._set_christian_service_flag("hourly_verse_notifications", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("auto_awesome"),
                "Hourly random verse",
                "Show a random Bible verse notification once every hour.",
                self.icon_font,
                self.ui_font,
                hourly_verse_switch,
            )
        )
        self.christian_next_devotion_switch = next_devotion_switch
        self.christian_hourly_verse_switch = hourly_verse_switch
        section = ExpandableServiceSection(
            "christian_widget",
            "Christian Widget",
            "Enable the devotion widget, surface it on the bar, and control its desktop notifications.",
            material_icon("auto_awesome"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("christian_widget"),
            lambda enabled: self._set_service_enabled("christian_widget", enabled),
        )
        self.service_sections["christian_widget"] = section
        return section

    def _build_weather_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.weather_city_input = QLineEdit(self.settings_state["weather"].get("name", ""))
        if self._selected_weather_city is not None:
            self.weather_city_input.setText(self._selected_weather_city.label)
        self.weather_city_input.setPlaceholderText("Type a city, region, or country")
        self.weather_city_input.textEdited.connect(self._queue_weather_city_search)

        self.weather_city_model = QStringListModel(self)
        self.weather_city_completer = QCompleter(self.weather_city_model, self)
        self.weather_city_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.weather_city_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.weather_city_completer.activated[str].connect(self._select_weather_city)
        self.weather_city_input.setCompleter(self.weather_city_completer)

        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Forecast city",
                "Autocomplete search powered by Open-Meteo geocoding.",
                self.icon_font,
                self.ui_font,
                self.weather_city_input,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.weather_apply_button = QPushButton("Apply city")
        self.weather_apply_button.setObjectName("primaryButton")
        self.weather_apply_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.weather_apply_button.clicked.connect(self._save_weather_settings)
        buttons.addWidget(self.weather_apply_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.weather_status = QLabel("Weather popup is idle.")
        self.weather_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.weather_status.setWordWrap(True)
        layout.addWidget(self.weather_status)

        section = ExpandableServiceSection(
            "weather",
            "Weather",
            "Choose a city for the weather popup and the bar weather icon.",
            material_icon("partly_cloudy_day"),
            self.icon_font,
            self.ui_font,
            content,
            bool(self.settings_state["weather"].get("enabled", False)),
            self._set_weather_enabled,
        )
        self.weather_section = section
        return section

    def _build_calendar_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.calendar_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["calendar_widget"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        self.calendar_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("calendar_widget", enabled)
        )
        self.service_display_switches["calendar_widget"] = self.calendar_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a calendar launcher card in the notification center overview.",
                self.icon_font,
                self.ui_font,
                self.calendar_display_switch,
            )
        )

        self.calendar_week_numbers_switch = SwitchButton(
            bool(self.settings_state["calendar"].get("show_week_numbers", False))
        )
        self.calendar_week_numbers_switch.toggledValue.connect(self._set_calendar_show_week_numbers)
        layout.addWidget(
            SettingsRow(
                material_icon("calendar_month"),
                "Show week numbers",
                "Adds ISO week numbers to the stylized calendar grid.",
                self.icon_font,
                self.ui_font,
                self.calendar_week_numbers_switch,
            )
        )

        self.calendar_other_month_switch = SwitchButton(
            bool(self.settings_state["calendar"].get("show_other_month_days", True))
        )
        self.calendar_other_month_switch.toggledValue.connect(self._set_calendar_show_other_month_days)
        layout.addWidget(
            SettingsRow(
                material_icon("event_upcoming"),
                "Show adjacent month days",
                "Keep leading and trailing days visible for a fuller month view.",
                self.icon_font,
                self.ui_font,
                self.calendar_other_month_switch,
            )
        )

        self.calendar_first_day_combo = QComboBox()
        self.calendar_first_day_combo.setObjectName("settingsCombo")
        self.calendar_first_day_combo.addItem("Monday", "monday")
        self.calendar_first_day_combo.addItem("Sunday", "sunday")
        current_first_day = str(self.settings_state["calendar"].get("first_day_of_week", "monday"))
        index = self.calendar_first_day_combo.findData(current_first_day)
        self.calendar_first_day_combo.setCurrentIndex(max(0, index))
        self.calendar_first_day_combo.currentIndexChanged.connect(self._set_calendar_first_day)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "First day of week",
                "Choose how the popup month grid should begin.",
                self.icon_font,
                self.ui_font,
                self.calendar_first_day_combo,
            )
        )

        self.calendar_url_input = QLineEdit(self.settings_state["calendar"].get("caldav_url", ""))
        self.calendar_url_input.setPlaceholderText("https://dav.example.com/caldav/")
        self.calendar_user_input = QLineEdit(self.settings_state["calendar"].get("caldav_username", ""))
        self.calendar_user_input.setPlaceholderText("username")
        self.calendar_password_input = QLineEdit(self.settings_state["calendar"].get("caldav_password", ""))
        self.calendar_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.calendar_password_input.setPlaceholderText("Password or app password")
        layout.addWidget(SettingsRow(material_icon("web_asset"), "CalDAV URL", "Used to discover and sync remote calendars into qcal.", self.icon_font, self.ui_font, self.calendar_url_input))
        layout.addWidget(SettingsRow(material_icon("person"), "CalDAV username", "Account used for CalDAV discovery.", self.icon_font, self.ui_font, self.calendar_user_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "CalDAV password", "Stored so qcal can keep your event list wired up.", self.icon_font, self.ui_font, self.calendar_password_input))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.calendar_save_button = QPushButton("Save")
        self.calendar_save_button.setObjectName("secondaryButton")
        self.calendar_discover_button = QPushButton("Discover calendars")
        self.calendar_discover_button.setObjectName("primaryButton")
        self.calendar_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.calendar_discover_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.calendar_save_button.clicked.connect(self._save_calendar_settings)
        self.calendar_discover_button.clicked.connect(self._discover_calendar_calendars)
        buttons.addWidget(self.calendar_save_button)
        buttons.addWidget(self.calendar_discover_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.calendar_status = QLabel(
            str(self.settings_state["calendar"].get("last_sync_status", "")).strip() or "Calendar integration is idle."
        )
        self.calendar_status.setWordWrap(True)
        self.calendar_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.calendar_status)

        section = ExpandableServiceSection(
            "calendar_widget",
            "Calendar",
            "Style the calendar popup and connect CalDAV calendars for live events.",
            material_icon("calendar_month"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("calendar_widget"),
            lambda enabled: self._set_service_enabled("calendar_widget", enabled),
        )
        self.service_sections["calendar_widget"] = section
        return section

    def _build_reminders_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.reminders_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["reminders_widget"].get(
                    "show_in_notification_center",
                    False,
                )
            )
        )
        self.reminders_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("reminders_widget", enabled)
        )
        self.service_display_switches["reminders_widget"] = self.reminders_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a reminders launcher card beside the other overview widgets.",
                self.icon_font,
                self.ui_font,
                self.reminders_display_switch,
            )
        )

        self.reminders_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["reminders_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.reminders_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("reminders_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("notifications"),
                "Show on bar",
                "Adds a reminders icon to the bar so the widget can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.reminders_bar_switch,
            )
        )

        self.reminders_intensity_combo = QComboBox()
        self.reminders_intensity_combo.setObjectName("settingsCombo")
        self.reminders_intensity_combo.addItem("Quiet", "quiet")
        self.reminders_intensity_combo.addItem("Discrete", "discrete")
        self.reminders_intensity_combo.addItem("Very disturbing", "disturbing")
        current_intensity = str(self.settings_state["reminders"].get("default_intensity", "discrete"))
        intensity_index = self.reminders_intensity_combo.findData(current_intensity)
        self.reminders_intensity_combo.setCurrentIndex(max(0, intensity_index))
        self.reminders_intensity_combo.currentIndexChanged.connect(self._set_reminder_default_intensity)
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Default reminder style",
                "Quiet is subtle, discrete is standard, and very disturbing repeats aggressively.",
                self.icon_font,
                self.ui_font,
                self.reminders_intensity_combo,
            )
        )

        self.reminders_lead_slider = QSlider(Qt.Orientation.Horizontal)
        self.reminders_lead_slider.setRange(0, 120)
        self.reminders_lead_slider.setValue(int(self.settings_state["reminders"].get("default_lead_minutes", 20)))
        self.reminders_lead_slider.valueChanged.connect(self._set_reminder_default_lead_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("alarm"),
                "Lead time",
                "How many minutes before a tracked CalDAV event the reminders widget should surface it.",
                self.icon_font,
                self.ui_font,
                self.reminders_lead_slider,
            )
        )

        self.tea_label_input = QLineEdit(self.settings_state["reminders"].get("tea_label", "Tea"))
        self.tea_label_input.setPlaceholderText("Tea, eggs, rice, pasta...")
        layout.addWidget(
            SettingsRow(
                material_icon("coffee"),
                "Tea reminder label",
                "Default label for the quick kitchen timer inside the reminders widget.",
                self.icon_font,
                self.ui_font,
                self.tea_label_input,
            )
        )

        self.tea_minutes_slider = QSlider(Qt.Orientation.Horizontal)
        self.tea_minutes_slider.setRange(1, 30)
        self.tea_minutes_slider.setValue(int(self.settings_state["reminders"].get("tea_minutes", 5)))
        self.tea_minutes_slider.valueChanged.connect(self._set_tea_default_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Tea reminder minutes",
                "Sets the default duration for tea, eggs, or any quick custom timer.",
                self.icon_font,
                self.ui_font,
                self.tea_minutes_slider,
            )
        )

        self.reminders_status = QLabel(
            f"{len(self.settings_state['reminders'].get('tracked_events', []))} tracked CalDAV reminder(s) saved."
        )
        self.reminders_status.setWordWrap(True)
        self.reminders_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.reminders_status)

        self.reminders_save_button = QPushButton("Save reminder defaults")
        self.reminders_save_button.setObjectName("primaryButton")
        self.reminders_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reminders_save_button.clicked.connect(self._save_reminders_settings)
        layout.addWidget(self.reminders_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "reminders_widget",
            "Reminders",
            "Surface tracked CalDAV event reminders and configure how noisy they should be.",
            material_icon("alarm"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("reminders_widget"),
            lambda enabled: self._set_service_enabled("reminders_widget", enabled),
        )
        self.service_sections["reminders_widget"] = section
        return section

    def _build_pomodoro_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.pomodoro_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["pomodoro_widget"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.pomodoro_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("pomodoro_widget", enabled)
        )
        self.service_display_switches["pomodoro_widget"] = self.pomodoro_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a Pomodoro launcher card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_display_switch,
            )
        )

        self.pomodoro_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["pomodoro_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.pomodoro_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("pomodoro_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Show on bar",
                "Adds a Pomodoro icon to the bar so the timer can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_bar_switch,
            )
        )

        self.pomodoro_work_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_work_slider.setRange(5, 90)
        self.pomodoro_work_slider.setValue(int(self.settings_state["pomodoro"].get("work_minutes", 25)))
        self.pomodoro_work_slider.valueChanged.connect(self._set_pomodoro_work_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("timer"),
                "Work minutes",
                "Length of each focus session before a break begins.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_work_slider,
            )
        )

        self.pomodoro_short_break_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_short_break_slider.setRange(1, 30)
        self.pomodoro_short_break_slider.setValue(int(self.settings_state["pomodoro"].get("short_break_minutes", 5)))
        self.pomodoro_short_break_slider.valueChanged.connect(self._set_pomodoro_short_break_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("coffee"),
                "Short break minutes",
                "Quick reset break used between most work sessions.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_short_break_slider,
            )
        )

        self.pomodoro_long_break_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_long_break_slider.setRange(5, 60)
        self.pomodoro_long_break_slider.setValue(int(self.settings_state["pomodoro"].get("long_break_minutes", 15)))
        self.pomodoro_long_break_slider.valueChanged.connect(self._set_pomodoro_long_break_minutes)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Long break minutes",
                "Recovery break used after a full Pomodoro cycle.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_long_break_slider,
            )
        )

        self.pomodoro_cycle_slider = QSlider(Qt.Orientation.Horizontal)
        self.pomodoro_cycle_slider.setRange(2, 8)
        self.pomodoro_cycle_slider.setValue(int(self.settings_state["pomodoro"].get("long_break_every", 4)))
        self.pomodoro_cycle_slider.valueChanged.connect(self._set_pomodoro_long_break_every)
        layout.addWidget(
            SettingsRow(
                material_icon("alarm"),
                "Long break every",
                "How many completed focus sessions should happen before the long break.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_cycle_slider,
            )
        )

        self.pomodoro_auto_breaks_switch = SwitchButton(
            bool(self.settings_state["pomodoro"].get("auto_start_breaks", False))
        )
        self.pomodoro_auto_breaks_switch.toggledValue.connect(self._set_pomodoro_auto_start_breaks)
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Auto-start breaks",
                "Start short and long break timers automatically when work ends.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_auto_breaks_switch,
            )
        )

        self.pomodoro_auto_focus_switch = SwitchButton(
            bool(self.settings_state["pomodoro"].get("auto_start_focus", False))
        )
        self.pomodoro_auto_focus_switch.toggledValue.connect(self._set_pomodoro_auto_start_focus)
        layout.addWidget(
            SettingsRow(
                material_icon("auto_awesome"),
                "Auto-start focus",
                "Begin the next work session automatically after a break ends.",
                self.icon_font,
                self.ui_font,
                self.pomodoro_auto_focus_switch,
            )
        )

        self.pomodoro_status = QLabel("Pomodoro widget defaults are ready.")
        self.pomodoro_status.setWordWrap(True)
        self.pomodoro_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.pomodoro_status)

        section = ExpandableServiceSection(
            "pomodoro_widget",
            "Pomodoro",
            "Run a focused work timer with quick breaks, a progress ring, and Matugen-aware styling.",
            material_icon("timer"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("pomodoro_widget"),
            lambda enabled: self._set_service_enabled("pomodoro_widget", enabled),
        )
        self.service_sections["pomodoro_widget"] = section
        return section

    def _build_rss_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.rss_display_switch = SwitchButton(
            bool(
                self.settings_state["services"]["rss_widget"].get(
                    "show_in_notification_center",
                    True,
                )
            )
        )
        self.rss_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("rss_widget", enabled)
        )
        self.service_display_switches["rss_widget"] = self.rss_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose an RSS launcher card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.rss_display_switch,
            )
        )

        self.rss_bar_switch = SwitchButton(
            bool(
                self.settings_state["services"]["rss_widget"].get(
                    "show_in_bar",
                    False,
                )
            )
        )
        self.rss_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("rss_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("public"),
                "Show on bar",
                "Adds an RSS icon to the bar so the feed reader can be opened directly.",
                self.icon_font,
                self.ui_font,
                self.rss_bar_switch,
            )
        )

        self.rss_urls_input = QLineEdit(self.settings_state["rss"].get("feed_urls", ""))
        self.rss_urls_input.setPlaceholderText("https://feed1.xml, https://feed2.xml")
        layout.addWidget(
            SettingsRow(
                material_icon("web_asset"),
                "Feed URLs",
                "Comma-separated RSS or Atom feed URLs if you want to manage feeds manually, including feeds exposed by self-hosted readers like FreshRSS.",
                self.icon_font,
                self.ui_font,
                self.rss_urls_input,
            )
        )

        self.rss_opml_input = QLineEdit(self.settings_state["rss"].get("opml_source", ""))
        self.rss_opml_input.setPlaceholderText("/path/to/feeds.opml or https://service.example/opml")
        layout.addWidget(
            SettingsRow(
                material_icon("folder_open"),
                "OPML source",
                "Local or remote OPML export. This works well with self-hosted readers like FreshRSS, which support OPML import and export.",
                self.icon_font,
                self.ui_font,
                self.rss_opml_input,
            )
        )

        self.rss_username_input = QLineEdit(self.settings_state["rss"].get("username", ""))
        self.rss_username_input.setPlaceholderText("Optional username")
        self.rss_password_input = QLineEdit(self.settings_state["rss"].get("password", ""))
        self.rss_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.rss_password_input.setPlaceholderText("Optional password")
        layout.addWidget(SettingsRow(material_icon("person"), "Username", "Used for basic-auth protected OPML or feed sources.", self.icon_font, self.ui_font, self.rss_username_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "Password", "Used for basic-auth protected OPML or feed sources.", self.icon_font, self.ui_font, self.rss_password_input))

        self.rss_limit_slider = QSlider(Qt.Orientation.Horizontal)
        self.rss_limit_slider.setRange(3, 30)
        self.rss_limit_slider.setValue(int(self.settings_state["rss"].get("item_limit", 10)))
        self.rss_limit_slider.valueChanged.connect(self._set_rss_item_limit)
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Item limit",
                "How many recent stories the RSS widget should surface at once.",
                self.icon_font,
                self.ui_font,
                self.rss_limit_slider,
            )
        )

        self.rss_interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.rss_interval_slider.setRange(5, 180)
        self.rss_interval_slider.setValue(int(self.settings_state["rss"].get("check_interval_minutes", 15)))
        self.rss_interval_slider.valueChanged.connect(self._set_rss_check_interval)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Check interval",
                "How often Hanauta checks your feeds for new entries and notifications.",
                self.icon_font,
                self.ui_font,
                self.rss_interval_slider,
            )
        )

        self.rss_notify_switch = SwitchButton(bool(self.settings_state["rss"].get("notify_new_items", True)))
        self.rss_notify_switch.toggledValue.connect(self._set_rss_notify_new_items)
        layout.addWidget(
            SettingsRow(
                material_icon("notifications_active"),
                "Notify on new stories",
                "Send a desktop notification for newly discovered RSS items, with a button to read them.",
                self.icon_font,
                self.ui_font,
                self.rss_notify_switch,
            )
        )

        self.rss_status = QLabel("RSS widget sources are ready.")
        self.rss_status.setWordWrap(True)
        self.rss_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.rss_status)

        self.rss_save_button = QPushButton("Save RSS sources")
        self.rss_save_button.setObjectName("primaryButton")
        self.rss_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rss_save_button.clicked.connect(self._save_rss_settings)
        layout.addWidget(self.rss_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "rss_widget",
            "RSS",
            "Read headlines from manual feeds or OPML exports, including self-hosted reader exports.",
            material_icon("web_asset"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("rss_widget"),
            lambda enabled: self._set_service_enabled("rss_widget", enabled),
        )
        self.service_sections["rss_widget"] = section
        return section

    def _build_obs_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.obs_display_switch = SwitchButton(
            bool(self.settings_state["services"]["obs_widget"].get("show_in_notification_center", True))
        )
        self.obs_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("obs_widget", enabled)
        )
        self.service_display_switches["obs_widget"] = self.obs_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the OBS control surface in the overview page.",
                self.icon_font,
                self.ui_font,
                self.obs_display_switch,
            )
        )

        self.obs_bar_switch = SwitchButton(
            bool(self.settings_state["services"]["obs_widget"].get("show_in_bar", False))
        )
        self.obs_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("obs_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("videocam"),
                "Show on bar",
                "Adds an OBS icon to the bar so streaming controls are one click away.",
                self.icon_font,
                self.ui_font,
                self.obs_bar_switch,
            )
        )

        self.obs_host_input = QLineEdit(self.settings_state["obs"].get("host", "127.0.0.1"))
        self.obs_port_input = QLineEdit(str(self.settings_state["obs"].get("port", 4455)))
        self.obs_password_input = QLineEdit(self.settings_state["obs"].get("password", ""))
        self.obs_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.obs_auto_connect_switch = SwitchButton(bool(self.settings_state["obs"].get("auto_connect", False)))
        self.obs_auto_connect_switch.toggledValue.connect(self._set_obs_auto_connect)
        layout.addWidget(SettingsRow(material_icon("public"), "OBS host", "OBS WebSocket host, usually 127.0.0.1.", self.icon_font, self.ui_font, self.obs_host_input))
        layout.addWidget(SettingsRow(material_icon("sensors"), "OBS port", "OBS WebSocket port. OBS 30+ defaults to 4455.", self.icon_font, self.ui_font, self.obs_port_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "OBS password", "Optional OBS WebSocket password.", self.icon_font, self.ui_font, self.obs_password_input))
        layout.addWidget(
            SettingsRow(
                material_icon("refresh"),
                "Connect when opened",
                "Try connecting to OBS as soon as the widget opens.",
                self.icon_font,
                self.ui_font,
                self.obs_auto_connect_switch,
            )
        )

        self.obs_status = QLabel("OBS widget is ready for local WebSocket control.")
        self.obs_status.setWordWrap(True)
        self.obs_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.obs_status)

        self.obs_save_button = QPushButton("Save OBS settings")
        self.obs_save_button.setObjectName("primaryButton")
        self.obs_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.obs_save_button.clicked.connect(self._save_obs_settings)
        layout.addWidget(self.obs_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "obs_widget",
            "OBS",
            "Livestreaming and recording controls powered by OBS WebSocket, with scene awareness and stream toggles.",
            material_icon("videocam"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("obs_widget"),
            lambda enabled: self._set_service_enabled("obs_widget", enabled),
        )
        self.service_sections["obs_widget"] = section
        return section

    def _build_crypto_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.crypto_display_switch = SwitchButton(
            bool(self.settings_state["services"]["crypto_widget"].get("show_in_notification_center", True))
        )
        self.crypto_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("crypto_widget", enabled)
        )
        self.service_display_switches["crypto_widget"] = self.crypto_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the crypto tracker card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.crypto_display_switch,
            )
        )

        self.crypto_bar_switch = SwitchButton(
            bool(self.settings_state["services"]["crypto_widget"].get("show_in_bar", False))
        )
        self.crypto_bar_switch.toggledValue.connect(
            lambda enabled: self._set_service_bar_visibility("crypto_widget", enabled)
        )
        layout.addWidget(
            SettingsRow(
                material_icon("show_chart"),
                "Show on bar",
                "Adds a crypto icon to the bar so you can open the tracker quickly.",
                self.icon_font,
                self.ui_font,
                self.crypto_bar_switch,
            )
        )

        self.crypto_coins_input = QLineEdit(self.settings_state["crypto"].get("tracked_coins", "bitcoin,ethereum"))
        self.crypto_coins_input.setPlaceholderText("bitcoin,ethereum,solana")
        self.crypto_currency_input = QLineEdit(self.settings_state["crypto"].get("vs_currency", "usd"))
        self.crypto_currency_input.setPlaceholderText("usd")
        self.crypto_api_key_input = QLineEdit(self.settings_state["crypto"].get("api_key", ""))
        self.crypto_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.crypto_api_key_input.setPlaceholderText("Optional CoinGecko Demo API key")
        layout.addWidget(SettingsRow(material_icon("show_chart"), "Tracked coins", "Comma-separated CoinGecko coin ids like bitcoin, ethereum, solana.", self.icon_font, self.ui_font, self.crypto_coins_input))
        layout.addWidget(SettingsRow(material_icon("public"), "Quote currency", "The currency used for pricing, such as usd or brl.", self.icon_font, self.ui_font, self.crypto_currency_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "CoinGecko Demo key", "Optional free demo key for higher limits. Hanauta uses CoinGecko for price and chart data.", self.icon_font, self.ui_font, self.crypto_api_key_input))

        self.crypto_interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_interval_slider.setRange(5, 180)
        self.crypto_interval_slider.setValue(int(self.settings_state["crypto"].get("check_interval_minutes", 15)))
        self.crypto_interval_slider.valueChanged.connect(self._set_crypto_check_interval)
        layout.addWidget(SettingsRow(material_icon("refresh"), "Check interval", "How often Hanauta checks tracked coins for fresh prices and alert-worthy moves.", self.icon_font, self.ui_font, self.crypto_interval_slider))

        self.crypto_chart_days_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_chart_days_slider.setRange(1, 90)
        self.crypto_chart_days_slider.setValue(int(self.settings_state["crypto"].get("chart_days", 7)))
        self.crypto_chart_days_slider.valueChanged.connect(self._set_crypto_chart_days)
        layout.addWidget(SettingsRow(material_icon("calendar_month"), "Chart days", "How many recent days the high-resolution chart should cover by default.", self.icon_font, self.ui_font, self.crypto_chart_days_slider))

        self.crypto_alert_switch = SwitchButton(bool(self.settings_state["crypto"].get("notify_price_moves", True)))
        self.crypto_alert_switch.toggledValue.connect(self._set_crypto_notify_price_moves)
        layout.addWidget(SettingsRow(material_icon("notifications_active"), "Price alerts", "Send notifications when tracked coins move beyond your up/down thresholds.", self.icon_font, self.ui_font, self.crypto_alert_switch))

        self.crypto_up_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_up_slider.setRange(1, 20)
        self.crypto_up_slider.setValue(int(round(float(self.settings_state["crypto"].get("price_up_percent", 3.0)))))
        self.crypto_up_slider.valueChanged.connect(self._set_crypto_up_percent)
        layout.addWidget(SettingsRow(material_icon("bolt"), "Up alert threshold", "Notify when a tracked coin rises by at least this percent since the previous check.", self.icon_font, self.ui_font, self.crypto_up_slider))

        self.crypto_down_slider = QSlider(Qt.Orientation.Horizontal)
        self.crypto_down_slider.setRange(1, 20)
        self.crypto_down_slider.setValue(int(round(float(self.settings_state["crypto"].get("price_down_percent", 3.0)))))
        self.crypto_down_slider.valueChanged.connect(self._set_crypto_down_percent)
        layout.addWidget(SettingsRow(material_icon("bolt"), "Down alert threshold", "Notify when a tracked coin falls by at least this percent since the previous check.", self.icon_font, self.ui_font, self.crypto_down_slider))

        self.crypto_status = QLabel("Crypto tracker is set to CoinGecko pricing.")
        self.crypto_status.setWordWrap(True)
        self.crypto_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.crypto_status)

        self.crypto_save_button = QPushButton("Save crypto settings")
        self.crypto_save_button.setObjectName("primaryButton")
        self.crypto_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.crypto_save_button.clicked.connect(self._save_crypto_settings)
        layout.addWidget(self.crypto_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "crypto_widget",
            "Crypto Tracker",
            "Track several coins, view a high-resolution chart, and get alerts when prices move.",
            material_icon("show_chart"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("crypto_widget"),
            lambda enabled: self._set_service_enabled("crypto_widget", enabled),
        )
        self.service_sections["crypto_widget"] = section
        return section

    def _build_vps_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.vps_display_switch = SwitchButton(
            bool(self.settings_state["services"]["vps_widget"].get("show_in_notification_center", True))
        )
        self.vps_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("vps_widget", enabled)
        )
        self.service_display_switches["vps_widget"] = self.vps_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose a VPS operations card in the overview page.",
                self.icon_font,
                self.ui_font,
                self.vps_display_switch,
            )
        )

        self.vps_host_input = QLineEdit(self.settings_state["vps"].get("host", ""))
        self.vps_port_input = QLineEdit(str(self.settings_state["vps"].get("port", 22)))
        self.vps_username_input = QLineEdit(self.settings_state["vps"].get("username", ""))
        self.vps_identity_input = QLineEdit(self.settings_state["vps"].get("identity_file", ""))
        self.vps_service_input = QLineEdit(self.settings_state["vps"].get("app_service", ""))
        self.vps_health_input = QLineEdit(self.settings_state["vps"].get("health_command", "uptime && df -h /"))
        self.vps_update_input = QLineEdit(self.settings_state["vps"].get("update_command", "sudo apt update && sudo apt upgrade -y"))
        layout.addWidget(SettingsRow(material_icon("public"), "Host", "Server host or IP for SSH connections.", self.icon_font, self.ui_font, self.vps_host_input))
        layout.addWidget(SettingsRow(material_icon("sensors"), "Port", "SSH port for the VPS.", self.icon_font, self.ui_font, self.vps_port_input))
        layout.addWidget(SettingsRow(material_icon("person"), "Username", "SSH username.", self.icon_font, self.ui_font, self.vps_username_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "Identity file", "Optional SSH private key path if you do not want to rely on your default agent.", self.icon_font, self.ui_font, self.vps_identity_input))
        layout.addWidget(SettingsRow(material_icon("hub"), "App service", "Optional systemd service to restart or check quickly, like caddy or myapp.service.", self.icon_font, self.ui_font, self.vps_service_input))
        layout.addWidget(SettingsRow(material_icon("terminal"), "Health command", "Command used by the widget to collect uptime, disk, and service health.", self.icon_font, self.ui_font, self.vps_health_input))
        layout.addWidget(SettingsRow(material_icon("refresh"), "Update command", "Command used when you want Hanauta to run package updates over SSH.", self.icon_font, self.ui_font, self.vps_update_input))

        self.vps_status = QLabel("VPS widget can run SSH health checks and maintenance commands.")
        self.vps_status.setWordWrap(True)
        self.vps_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.vps_status)

        self.vps_save_button = QPushButton("Save VPS settings")
        self.vps_save_button.setObjectName("primaryButton")
        self.vps_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.vps_save_button.clicked.connect(self._save_vps_settings)
        layout.addWidget(self.vps_save_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "vps_widget",
            "VPS Care",
            "SSH into your VPS health workflow for checks, package updates, and service restarts.",
            material_icon("storage"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("vps_widget"),
            lambda enabled: self._set_service_enabled("vps_widget", enabled),
        )
        self.service_sections["vps_widget"] = section
        return section

    def _build_desktop_clock_service_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.clock_display_switch = SwitchButton(
            bool(self.settings_state["services"]["desktop_clock_widget"].get("show_in_notification_center", True))
        )
        self.clock_display_switch.toggledValue.connect(
            lambda enabled: self._set_service_notification_visibility("desktop_clock_widget", enabled)
        )
        self.service_display_switches["desktop_clock_widget"] = self.clock_display_switch
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show in notification center",
                "Expose the desktop clock launcher in the overview page.",
                self.icon_font,
                self.ui_font,
                self.clock_display_switch,
            )
        )

        self.clock_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.clock_size_slider.setRange(220, 520)
        self.clock_size_slider.setValue(int(self.settings_state["clock"].get("size", 320)))
        self.clock_size_slider.valueChanged.connect(self._set_clock_size)
        layout.addWidget(
            SettingsRow(
                material_icon("crop_square"),
                "Clock size",
                "Resize the desktop clock without changing its design language.",
                self.icon_font,
                self.ui_font,
                self.clock_size_slider,
            )
        )

        self.clock_seconds_switch = SwitchButton(bool(self.settings_state["clock"].get("show_seconds", True)))
        self.clock_seconds_switch.toggledValue.connect(self._set_clock_show_seconds)
        layout.addWidget(
            SettingsRow(
                material_icon("schedule"),
                "Show seconds hand",
                "Display the slim moving seconds hand on the analog clock face.",
                self.icon_font,
                self.ui_font,
                self.clock_seconds_switch,
            )
        )

        self.clock_status = QLabel("Desktop clock is ready.")
        self.clock_status.setWordWrap(True)
        self.clock_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        layout.addWidget(self.clock_status)

        self.clock_reset_button = QPushButton("Reset clock position")
        self.clock_reset_button.setObjectName("secondaryButton")
        self.clock_reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clock_reset_button.clicked.connect(self._reset_clock_position)
        layout.addWidget(self.clock_reset_button, 0, Qt.AlignmentFlag.AlignLeft)

        section = ExpandableServiceSection(
            "desktop_clock_widget",
            "Desktop Clock",
            "A Hanauta-native analog and digital desktop clock with a sculpted face and Matugen colors.",
            material_icon("watch"),
            self.icon_font,
            self.ui_font,
            content,
            self._service_enabled("desktop_clock_widget"),
            lambda enabled: self._set_service_enabled("desktop_clock_widget", enabled),
        )
        self.service_sections["desktop_clock_widget"] = section
        return section

    def _build_ntfy_section(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.ntfy_server_input = QLineEdit(self.settings_state["ntfy"].get("server_url", "https://ntfy.sh"))
        self.ntfy_server_input.setPlaceholderText("https://ntfy.sh")
        self.ntfy_topic_input = QLineEdit(self.settings_state["ntfy"].get("topic", ""))
        self.ntfy_topic_input.setPlaceholderText("alerts-topic")
        self.ntfy_token_input = QLineEdit(self.settings_state["ntfy"].get("token", ""))
        self.ntfy_token_input.setPlaceholderText("Access token")
        self.ntfy_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ntfy_username_input = QLineEdit(self.settings_state["ntfy"].get("username", ""))
        self.ntfy_username_input.setPlaceholderText("Username (optional)")
        self.ntfy_password_input = QLineEdit(self.settings_state["ntfy"].get("password", ""))
        self.ntfy_password_input.setPlaceholderText("Password (optional)")
        self.ntfy_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addWidget(SettingsRow(material_icon("web_asset"), "Server URL", "Custom ntfy instance URL.", self.icon_font, self.ui_font, self.ntfy_server_input))
        layout.addWidget(SettingsRow(material_icon("hub"), "Default topic", "Topic used by the bar publisher and test sends.", self.icon_font, self.ui_font, self.ntfy_topic_input))
        layout.addWidget(SettingsRow(material_icon("bolt"), "Access token", "Bearer token for ntfy authentication if required.", self.icon_font, self.ui_font, self.ntfy_token_input))
        layout.addWidget(SettingsRow(material_icon("person"), "Username", "Optional basic auth username.", self.icon_font, self.ui_font, self.ntfy_username_input))
        layout.addWidget(SettingsRow(material_icon("lock"), "Password", "Optional basic auth password.", self.icon_font, self.ui_font, self.ntfy_password_input))

        self.ntfy_bar_switch = SwitchButton(bool(self.settings_state["ntfy"].get("show_in_bar", False)))
        self.ntfy_bar_switch.toggledValue.connect(self._set_ntfy_show_in_bar)
        layout.addWidget(
            SettingsRow(
                material_icon("widgets"),
                "Show on bar",
                "Display an ntfy publish icon on the bar.",
                self.icon_font,
                self.ui_font,
                self.ntfy_bar_switch,
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.ntfy_save_button = QPushButton("Save")
        self.ntfy_test_button = QPushButton("Send Test")
        self.ntfy_save_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ntfy_test_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ntfy_save_button.clicked.connect(self._save_ntfy_settings)
        self.ntfy_test_button.clicked.connect(self._send_ntfy_test)
        buttons.addWidget(self.ntfy_save_button)
        buttons.addWidget(self.ntfy_test_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.ntfy_status = QLabel("ntfy integration is idle.")
        self.ntfy_status.setStyleSheet("color: rgba(246,235,247,0.72);")
        self.ntfy_status.setWordWrap(True)
        layout.addWidget(self.ntfy_status)

        section = ExpandableServiceSection(
            "ntfy",
            "ntfy",
            "Custom ntfy server, topics, credentials, and an optional bar publisher icon.",
            material_icon("notifications"),
            self.icon_font,
            self.ui_font,
            content,
            bool(self.settings_state["ntfy"].get("enabled", False)),
            self._set_ntfy_enabled,
        )
        self.ntfy_section = section
        return section

    def _service_enabled(self, key: str) -> bool:
        return bool(self.settings_state["services"].get(key, {}).get("enabled", True))

    def _set_service_enabled(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        service["enabled"] = bool(enabled)
        if not enabled:
            service["show_in_notification_center"] = False
            if key == "vpn_control":
                service["reconnect_on_login"] = False
            if key == "christian_widget":
                service["show_in_bar"] = False
                service["next_devotion_notifications"] = False
                service["hourly_verse_notifications"] = False
            if key in {"reminders_widget", "pomodoro_widget", "rss_widget", "obs_widget", "crypto_widget"}:
                service["show_in_bar"] = False
        save_settings_state(self.settings_state)
        section = getattr(self, "service_sections", {}).get(key)
        if section is not None:
            section.set_enabled(enabled)
        display_switch = getattr(self, "service_display_switches", {}).get(key)
        if display_switch is not None:
            if key == "christian_widget":
                display_switch.setChecked(bool(service.get("show_in_bar", False)))
            else:
                display_switch.setChecked(bool(service.get("show_in_notification_center", False)))
            display_switch._apply_state()
        if key == "christian_widget":
            for attr_name, setting_key in (
                ("christian_next_devotion_switch", "next_devotion_notifications"),
                ("christian_hourly_verse_switch", "hourly_verse_notifications"),
            ):
                switch = getattr(self, attr_name, None)
                if switch is not None:
                    switch.setChecked(bool(service.get(setting_key, False)))
                    switch._apply_state()
        if key in {"calendar_widget", "reminders_widget", "pomodoro_widget", "obs_widget", "crypto_widget", "vps_widget", "desktop_clock_widget"}:
            display_switch = getattr(self, "service_display_switches", {}).get(key)
            if display_switch is not None:
                display_switch.setChecked(bool(service.get("show_in_notification_center", False)))
                display_switch._apply_state()
        if key == "vpn_control":
            switch = getattr(self, "vpn_reconnect_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("reconnect_on_login", False)))
                switch._apply_state()
        if key == "reminders_widget":
            switch = getattr(self, "reminders_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "pomodoro_widget":
            switch = getattr(self, "pomodoro_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "rss_widget":
            switch = getattr(self, "rss_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "obs_widget":
            switch = getattr(self, "obs_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()
        if key == "crypto_widget":
            switch = getattr(self, "crypto_bar_switch", None)
            if switch is not None:
                switch.setChecked(bool(service.get("show_in_bar", False)))
                switch._apply_state()

    def _set_service_notification_visibility(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        if not service.get("enabled", True):
            return
        service["show_in_notification_center"] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_service_bar_visibility(self, key: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault(key, {})
        if not service.get("enabled", True):
            return
        service["show_in_bar"] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_christian_service_flag(self, flag: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("christian_widget", {})
        if not service.get("enabled", True):
            return
        service[flag] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_vpn_service_flag(self, flag: str, enabled: bool) -> None:
        service = self.settings_state["services"].setdefault("vpn_control", {})
        if not service.get("enabled", True):
            return
        service[flag] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_calendar_show_week_numbers(self, enabled: bool) -> None:
        self.settings_state.setdefault("calendar", {})["show_week_numbers"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar week numbers updated.")

    def _set_calendar_show_other_month_days(self, enabled: bool) -> None:
        self.settings_state.setdefault("calendar", {})["show_other_month_days"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar adjacent-month visibility updated.")

    def _set_calendar_first_day(self, index: int) -> None:
        value = self.calendar_first_day_combo.itemData(index) if hasattr(self, "calendar_first_day_combo") else "monday"
        self.settings_state.setdefault("calendar", {})["first_day_of_week"] = str(value or "monday")
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar first day updated.")

    def _save_calendar_settings(self) -> None:
        calendar = self.settings_state.setdefault("calendar", {})
        calendar["caldav_url"] = self.calendar_url_input.text().strip()
        calendar["caldav_username"] = self.calendar_user_input.text().strip()
        calendar["caldav_password"] = self.calendar_password_input.text()
        save_settings_state(self.settings_state)
        if hasattr(self, "calendar_status"):
            self.calendar_status.setText("Calendar settings saved.")

    def _discover_calendar_calendars(self) -> None:
        self._save_calendar_settings()
        calendar = self.settings_state.setdefault("calendar", {})
        url = str(calendar.get("caldav_url", "")).strip()
        username = str(calendar.get("caldav_username", "")).strip()
        password = str(calendar.get("caldav_password", ""))
        if not url or not username or not password:
            self.calendar_status.setText("CalDAV URL, username, and password are required.")
            return
        if not QCAL_WRAPPER.exists():
            self.calendar_status.setText("qcal wrapper is missing.")
            return
        result = subprocess.run(
            [sys.executable, str(QCAL_WRAPPER), "discover", url, username, password],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout or "{}")
        except Exception:
            payload = {"success": False, "error": (result.stderr or "CalDAV discovery failed.").strip()}
        success = bool(payload.get("success", False))
        calendar["connected"] = success
        names = payload.get("calendars", [])
        if success:
            discovered = ", ".join(str(name) for name in names[:3])
            suffix = "" if len(names) <= 3 else "..."
            calendar["last_sync_status"] = f"Connected to {len(names)} calendar(s): {discovered}{suffix}"
        else:
            calendar["last_sync_status"] = str(payload.get("error", "Unable to discover calendars.")).strip()
        save_settings_state(self.settings_state)
        self.calendar_status.setText(calendar["last_sync_status"] or "Calendar integration updated.")

    def _set_reminder_default_intensity(self, index: int) -> None:
        value = self.reminders_intensity_combo.itemData(index) if hasattr(self, "reminders_intensity_combo") else "discrete"
        self.settings_state.setdefault("reminders", {})["default_intensity"] = str(value or "discrete")
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()

    def _set_reminder_default_lead_minutes(self, value: int) -> None:
        self.settings_state.setdefault("reminders", {})["default_lead_minutes"] = int(value)
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()

    def _set_tea_default_minutes(self, value: int) -> None:
        self.settings_state.setdefault("reminders", {})["tea_minutes"] = int(value)
        save_settings_state(self.settings_state)
        self._refresh_reminders_status()

    def _set_pomodoro_work_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["work_minutes"] = max(5, min(90, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Work sessions set to {int(value)} minute(s).")

    def _set_pomodoro_short_break_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["short_break_minutes"] = max(1, min(30, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Short breaks set to {int(value)} minute(s).")

    def _set_pomodoro_long_break_minutes(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["long_break_minutes"] = max(5, min(60, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Long breaks set to {int(value)} minute(s).")

    def _set_pomodoro_long_break_every(self, value: int) -> None:
        self.settings_state.setdefault("pomodoro", {})["long_break_every"] = max(2, min(8, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(f"Long break cadence set to every {int(value)} focus session(s).")

    def _set_pomodoro_auto_start_breaks(self, enabled: bool) -> None:
        self.settings_state.setdefault("pomodoro", {})["auto_start_breaks"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                "Break timers will auto-start after work sessions." if enabled else "Break timers now wait for manual start."
            )

    def _set_pomodoro_auto_start_focus(self, enabled: bool) -> None:
        self.settings_state.setdefault("pomodoro", {})["auto_start_focus"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "pomodoro_status"):
            self.pomodoro_status.setText(
                "Focus sessions will auto-start after breaks." if enabled else "Focus sessions now wait for manual start."
            )

    def _set_rss_item_limit(self, value: int) -> None:
        self.settings_state.setdefault("rss", {})["item_limit"] = max(3, min(30, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText(f"RSS item limit set to {int(value)} story entries.")

    def _set_rss_check_interval(self, value: int) -> None:
        self.settings_state.setdefault("rss", {})["check_interval_minutes"] = max(5, min(180, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText(f"RSS checks now run every {int(value)} minute(s).")

    def _set_rss_notify_new_items(self, enabled: bool) -> None:
        self.settings_state.setdefault("rss", {})["notify_new_items"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            self.rss_status.setText("RSS notifications are enabled." if enabled else "RSS notifications are paused.")

    def _save_rss_settings(self) -> None:
        rss = self.settings_state.setdefault("rss", {})
        rss["feed_urls"] = self.rss_urls_input.text().strip()
        rss["opml_source"] = self.rss_opml_input.text().strip()
        rss["username"] = self.rss_username_input.text().strip()
        rss["password"] = self.rss_password_input.text()
        rss["item_limit"] = int(self.rss_limit_slider.value())
        rss["check_interval_minutes"] = int(self.rss_interval_slider.value()) if hasattr(self, "rss_interval_slider") else 15
        rss["notify_new_items"] = bool(self.rss_notify_switch.isChecked()) if hasattr(self, "rss_notify_switch") else True
        save_settings_state(self.settings_state)
        if hasattr(self, "rss_status"):
            rss_mode = "manual feeds"
            if rss["opml_source"]:
                rss_mode = "OPML sync"
            self.rss_status.setText(f"RSS sources saved for {rss_mode}. Notifications stay on a {rss['check_interval_minutes']}-minute rhythm.")

    def _set_obs_auto_connect(self, enabled: bool) -> None:
        self.settings_state.setdefault("obs", {})["auto_connect"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "obs_status"):
            self.obs_status.setText("OBS widget will connect immediately when opened." if enabled else "OBS widget now waits for a manual connect.")

    def _save_obs_settings(self) -> None:
        obs = self.settings_state.setdefault("obs", {})
        obs["host"] = self.obs_host_input.text().strip() or "127.0.0.1"
        try:
            obs["port"] = max(1, min(65535, int(self.obs_port_input.text().strip() or "4455")))
        except Exception:
            obs["port"] = 4455
        obs["password"] = self.obs_password_input.text()
        obs["auto_connect"] = bool(self.obs_auto_connect_switch.isChecked())
        save_settings_state(self.settings_state)
        if hasattr(self, "obs_status"):
            self.obs_status.setText(f"OBS connection saved for {obs['host']}:{obs['port']}.")

    def _set_crypto_check_interval(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["check_interval_minutes"] = max(5, min(180, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(f"Crypto checks now run every {int(value)} minute(s).")

    def _set_crypto_chart_days(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["chart_days"] = max(1, min(90, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(f"Charts will open on the last {int(value)} day(s).")

    def _set_crypto_notify_price_moves(self, enabled: bool) -> None:
        self.settings_state.setdefault("crypto", {})["notify_price_moves"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText("Crypto move notifications are enabled." if enabled else "Crypto move notifications are paused.")

    def _set_crypto_up_percent(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["price_up_percent"] = float(max(1, min(20, int(value))))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(f"Up alerts will trigger at {int(value)}% or more.")

    def _set_crypto_down_percent(self, value: int) -> None:
        self.settings_state.setdefault("crypto", {})["price_down_percent"] = float(max(1, min(20, int(value))))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText(f"Down alerts will trigger at {int(value)}% or more.")

    def _save_crypto_settings(self) -> None:
        crypto = self.settings_state.setdefault("crypto", {})
        crypto["api_provider"] = "coingecko"
        crypto["api_key"] = self.crypto_api_key_input.text().strip()
        crypto["tracked_coins"] = self.crypto_coins_input.text().strip()
        crypto["vs_currency"] = self.crypto_currency_input.text().strip().lower() or "usd"
        crypto["check_interval_minutes"] = int(self.crypto_interval_slider.value())
        crypto["chart_days"] = int(self.crypto_chart_days_slider.value())
        crypto["notify_price_moves"] = bool(self.crypto_alert_switch.isChecked())
        crypto["price_up_percent"] = float(int(self.crypto_up_slider.value()))
        crypto["price_down_percent"] = float(int(self.crypto_down_slider.value()))
        save_settings_state(self.settings_state)
        if hasattr(self, "crypto_status"):
            self.crypto_status.setText("Crypto tracker settings saved for CoinGecko.")

    def _save_vps_settings(self) -> None:
        vps = self.settings_state.setdefault("vps", {})
        vps["host"] = self.vps_host_input.text().strip()
        try:
            vps["port"] = max(1, min(65535, int(self.vps_port_input.text().strip() or "22")))
        except Exception:
            vps["port"] = 22
        vps["username"] = self.vps_username_input.text().strip()
        vps["identity_file"] = self.vps_identity_input.text().strip()
        vps["app_service"] = self.vps_service_input.text().strip()
        vps["health_command"] = self.vps_health_input.text().strip() or "uptime && df -h /"
        vps["update_command"] = self.vps_update_input.text().strip() or "sudo apt update && sudo apt upgrade -y"
        save_settings_state(self.settings_state)
        if hasattr(self, "vps_status"):
            if vps["host"]:
                self.vps_status.setText(f"VPS connection saved for {vps['username']}@{vps['host']}:{vps['port']}.")
            else:
                self.vps_status.setText("VPS settings saved. Add a host when you are ready.")

    def _set_clock_size(self, value: int) -> None:
        self.settings_state.setdefault("clock", {})["size"] = max(220, min(520, int(value)))
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText(f"Desktop clock size set to {int(value)}px.")

    def _set_clock_show_seconds(self, enabled: bool) -> None:
        self.settings_state.setdefault("clock", {})["show_seconds"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText("Seconds hand enabled." if enabled else "Seconds hand hidden.")

    def _reset_clock_position(self) -> None:
        clock = self.settings_state.setdefault("clock", {})
        clock["position_x"] = -1
        clock["position_y"] = -1
        save_settings_state(self.settings_state)
        if hasattr(self, "clock_status"):
            self.clock_status.setText("Desktop clock position reset.")

    def _save_reminders_settings(self) -> None:
        reminders = self.settings_state.setdefault("reminders", {})
        reminders["tea_label"] = self.tea_label_input.text().strip() or "Tea"
        reminders["default_intensity"] = str(self.reminders_intensity_combo.currentData() or "discrete")
        reminders["default_lead_minutes"] = int(self.reminders_lead_slider.value())
        reminders["tea_minutes"] = int(self.tea_minutes_slider.value())
        save_settings_state(self.settings_state)
        self._refresh_reminders_status("Reminder defaults saved.")

    def _refresh_reminders_status(self, prefix: str = "") -> None:
        tracked_count = len(self.settings_state.get("reminders", {}).get("tracked_events", []))
        detail = (
            f"{tracked_count} tracked reminder(s) • "
            f"{self.settings_state['reminders'].get('default_lead_minutes', 20)} min lead • "
            f"{self.settings_state['reminders'].get('default_intensity', 'discrete')}"
        )
        self.reminders_status.setText(f"{prefix} {detail}".strip())

    def _set_ntfy_enabled(self, enabled: bool) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        ntfy["enabled"] = bool(enabled)
        if not enabled:
            ntfy["show_in_bar"] = False
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_bar_switch"):
            self.ntfy_bar_switch.setChecked(bool(ntfy.get("show_in_bar", False)))
            self.ntfy_bar_switch._apply_state()

    def _set_ntfy_show_in_bar(self, enabled: bool) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        if not ntfy.get("enabled", False):
            return
        ntfy["show_in_bar"] = bool(enabled)
        save_settings_state(self.settings_state)

    def _set_weather_enabled(self, enabled: bool) -> None:
        weather = self.settings_state.setdefault("weather", {})
        weather["enabled"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(
                "Weather icon enabled on the bar." if enabled else "Weather icon disabled."
            )

    def _set_region_use_24_hour(self, enabled: bool) -> None:
        self.settings_state.setdefault("region", {})["use_24_hour"] = bool(enabled)
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Clock format updated.")

    def _set_region_date_style(self, index: int) -> None:
        value = self.region_date_style_combo.itemData(index) if hasattr(self, "region_date_style_combo") else "us"
        self.settings_state.setdefault("region", {})["date_style"] = str(value or "us")
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Date style updated.")

    def _set_region_temperature_unit(self, index: int) -> None:
        value = self.region_temperature_combo.itemData(index) if hasattr(self, "region_temperature_combo") else "c"
        self.settings_state.setdefault("region", {})["temperature_unit"] = str(value or "c")
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            self.region_status.setText("Temperature unit updated.")

    def _save_region_settings(self) -> None:
        region = self.settings_state.setdefault("region", {})
        region["locale_code"] = self.region_locale_input.text().strip()
        region["use_24_hour"] = bool(self.region_24h_switch.isChecked())
        region["date_style"] = str(self.region_date_style_combo.currentData() or "us")
        region["temperature_unit"] = str(self.region_temperature_combo.currentData() or "c")
        save_settings_state(self.settings_state)
        if hasattr(self, "region_status"):
            locale_label = region["locale_code"] or "system default"
            self.region_status.setText(f"Region settings saved for {locale_label}.")

    def _save_bar_settings(self) -> None:
        self.settings_state["bar"] = merged_bar_settings(self.settings_state.get("bar", {}))
        save_settings_state(self.settings_state)

    def _set_bar_launcher_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["launcher_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_workspace_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["workspace_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_datetime_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["datetime_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_media_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["media_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_status_offset(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["status_offset"] = int(value)
        self._save_bar_settings()

    def _set_bar_height(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["bar_height"] = int(value)
        self._save_bar_settings()

    def _set_bar_chip_radius(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["chip_radius"] = int(value)
        self._save_bar_settings()

    def _set_bar_merge_all_chips(self, enabled: bool) -> None:
        self.settings_state.setdefault("bar", {})["merge_all_chips"] = bool(enabled)
        self._save_bar_settings()

    def _set_bar_full_radius(self, value: int) -> None:
        self.settings_state.setdefault("bar", {})["full_bar_radius"] = int(value)
        self._save_bar_settings()

    def _queue_weather_city_search(self, text: str) -> None:
        self._selected_weather_city = None
        if len(text.strip()) < 2:
            self.weather_city_model.setStringList([])
            return
        self._weather_search_timer.start(250)

    def _perform_weather_city_search(self) -> None:
        if not hasattr(self, "weather_city_input"):
            return
        text = self.weather_city_input.text().strip()
        if len(text) < 2:
            self.weather_city_model.setStringList([])
            return
        matches = search_cities(text)
        self._weather_city_map = {city.label: city for city in matches}
        labels = list(self._weather_city_map.keys())
        self.weather_city_model.setStringList(labels)
        if labels:
            self.weather_city_completer.complete()

    def _select_weather_city(self, label: str) -> None:
        city = self._weather_city_map.get(label)
        if city is None:
            return
        self._selected_weather_city = city
        self.weather_city_input.setText(label)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(f"Selected city: {label}")

    def _save_weather_settings(self) -> None:
        city = self._selected_weather_city
        current_text = self.weather_city_input.text().strip() if hasattr(self, "weather_city_input") else ""
        if city is None and current_text:
            city = self._weather_city_map.get(current_text)
        if city is None:
            if hasattr(self, "weather_status"):
                self.weather_status.setText("Pick a city from the autocomplete list first.")
            return
        weather = self.settings_state.setdefault("weather", {})
        weather.update(
            {
                "enabled": True,
                "name": city.name,
                "admin1": city.admin1,
                "country": city.country,
                "latitude": city.latitude,
                "longitude": city.longitude,
                "timezone": city.timezone,
            }
        )
        save_settings_state(self.settings_state)
        if hasattr(self, "weather_section"):
            self.weather_section.set_enabled(True)
        if hasattr(self, "weather_status"):
            self.weather_status.setText(f"Weather city saved: {city.label}")

    def _make_transparency_switch(self) -> SwitchButton:
        switch = SwitchButton(bool(self.settings_state["appearance"].get("transparency", True)))
        switch.toggledValue.connect(self._set_transparency)
        return switch

    def _make_matugen_switch(self) -> SwitchButton:
        switch = SwitchButton(bool(self.settings_state["appearance"].get("use_matugen_palette", False)))
        switch.toggledValue.connect(self._set_use_matugen_palette)
        self.matugen_palette_switch = switch
        return switch

    def _set_transparency(self, enabled: bool) -> None:
        self.settings_state["appearance"]["transparency"] = bool(enabled)
        save_settings_state(self.settings_state)
        self._apply_styles()

    def _set_use_matugen_palette(self, enabled: bool) -> None:
        self.settings_state["appearance"]["use_matugen_palette"] = bool(enabled)
        save_settings_state(self.settings_state)
        if enabled:
            self._apply_matugen_palette()
            self.theme_palette = load_theme_palette()
            self._theme_mtime = palette_mtime()
            self._refresh_current_accent()
            self._apply_styles()
            return
        write_default_pyqt_palette(use_matugen=False)
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._refresh_current_accent()
        self._apply_styles()

    def _set_theme_mode(self, mode: str) -> None:
        self.settings_state["appearance"]["theme_mode"] = mode
        save_settings_state(self.settings_state)
        self._sync_accent_controls()

    def _set_accent(self, key: str) -> None:
        key = {"auto": "orchid"}.get(key, key)
        self.settings_state["appearance"]["accent"] = key
        save_settings_state(self.settings_state)
        self._sync_accent_controls()
        self._apply_styles()

    def _sync_accent_controls(self) -> None:
        accent = self.settings_state["appearance"].get("accent", "orchid")
        for key, chip in getattr(self, "accent_chips", {}).items():
            chip.setChecked(key == accent or (key == "auto" and accent == "orchid"))
        theme_mode = self.settings_state["appearance"].get("theme_mode", "dark")
        for key, button in getattr(self, "theme_buttons", {}).items():
            button.setChecked(key == theme_mode)
        self._refresh_current_accent()

    def _refresh_current_accent(self) -> None:
        accent = self.settings_state["appearance"].get("accent", "orchid")
        self.current_accent = accent_palette(accent)
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme_palette = load_theme_palette()
        self._refresh_current_accent()
        self._apply_styles()

    def _sync_wallpaper_controls(self) -> None:
        if hasattr(self, "preview_card"):
            self.preview_card.update_wallpaper(self.wallpaper)
        if hasattr(self, "slideshow_button"):
            running = self._slideshow_timer.isActive()
            self.slideshow_button.set_content(
                material_icon("image"),
                "Stop slideshow" if running else "Start slideshow",
                "Rotate wallpapers from the selected folder" if not running else "Pause the current slideshow rotation",
            )

    def _save_appearance_state(self) -> None:
        self.settings_state["appearance"]["wallpaper_path"] = str(self.wallpaper)
        save_settings_state(self.settings_state)
        self._sync_wallpaper_controls()

    def _sync_wallpaper_source(self, source_key: str) -> None:
        if getattr(self, "_wallpaper_sync_worker", None) is not None:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText("Wallpaper sync is already running.")
            return
        if hasattr(self, "appearance_status"):
            preset = WALLPAPER_SOURCE_PRESETS.get(source_key, {})
            source_label = str(preset.get("label", "community source"))
            self.appearance_status.setText(f"Syncing wallpapers from {source_label}...")
        if hasattr(self, "wallpaper_sync_progress"):
            self.wallpaper_sync_progress.show()
        for button_name in ("sync_caelestia_button", "sync_end4_button"):
            button = getattr(self, button_name, None)
            if isinstance(button, QPushButton):
                button.setEnabled(False)
        self._wallpaper_sync_worker = WallpaperSourceSyncWorker(source_key)
        self._wallpaper_sync_worker.finished_sync.connect(self._finish_wallpaper_source_sync)
        self._wallpaper_sync_worker.finished.connect(self._cleanup_wallpaper_source_worker)
        self._wallpaper_sync_worker.start()

    def _finish_wallpaper_source_sync(self, _source_key: str, ok: bool, message: str, folder_obj: object) -> None:
        folder = folder_obj if isinstance(folder_obj, Path) else None
        if not ok or folder is None:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText(message)
            return
        self.settings_state["appearance"]["slideshow_folder"] = str(folder)
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        save_settings_state(self.settings_state)
        self._sync_wallpaper_controls()
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(f"{message} Slideshow folder now points to {folder}.")

    def _cleanup_wallpaper_source_worker(self) -> None:
        if hasattr(self, "wallpaper_sync_progress"):
            self.wallpaper_sync_progress.hide()
        for button_name in ("sync_caelestia_button", "sync_end4_button"):
            button = getattr(self, button_name, None)
            if isinstance(button, QPushButton):
                button.setEnabled(True)
        worker = getattr(self, "_wallpaper_sync_worker", None)
        if worker is not None:
            worker.deleteLater()
        self._wallpaper_sync_worker = None

    def _apply_matugen_palette(self, force: bool = False) -> None:
        if not self.wallpaper.exists() or not self.wallpaper.is_file():
            return
        if force and not self.settings_state["appearance"].get("use_matugen_palette", False):
            self.settings_state["appearance"]["use_matugen_palette"] = True
            save_settings_state(self.settings_state)
            if hasattr(self, "matugen_palette_switch"):
                self.matugen_palette_switch.setChecked(True)
                self.matugen_palette_switch._apply_state()
        if not self.settings_state["appearance"].get("use_matugen_palette", False):
            write_default_pyqt_palette(use_matugen=False)
            return
        if MATUGEN_SCRIPT.exists():
            run_bg([str(MATUGEN_SCRIPT), str(self.wallpaper)])

    def _wallpaper_mode_for_output(self, output_name: str) -> str:
        fit_modes = self.settings_state["appearance"].get("wallpaper_fit_modes", {})
        if not isinstance(fit_modes, dict):
            return "fill"
        return str(fit_modes.get(output_name, "fill"))

    def _apply_current_wallpaper_layout(self) -> None:
        if not self.wallpaper.exists() or not self.wallpaper.is_file():
            return
        active_displays = [display for display in parse_xrandr_state() if display.get("enabled")]
        if not active_displays:
            if WALLPAPER_SCRIPT.exists():
                run_bg([str(WALLPAPER_SCRIPT), str(self.wallpaper)])
            else:
                run_bg(["feh", "--bg-fill", str(self.wallpaper)])
            return
        rendered = self._render_wallpaper_variants(self.wallpaper, active_displays)
        if rendered:
            run_bg(["feh", "--bg-fill", *[str(path) for path in rendered]])
        elif WALLPAPER_SCRIPT.exists():
            run_bg([str(WALLPAPER_SCRIPT), str(self.wallpaper)])
        else:
            run_bg(["feh", "--bg-fill", str(self.wallpaper)])

    def _render_wallpaper_variants(self, path: Path, displays: list[dict]) -> list[Path]:
        source = QImage(str(path))
        if source.isNull():
            return []
        RENDERED_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
        rendered_paths: list[Path] = []
        for display in displays:
            mode_text = display.get("current_mode", "")
            if "x" not in mode_text:
                continue
            try:
                width_text, height_text = mode_text.split("x", 1)
                width = int(width_text)
                height = int(height_text)
            except Exception:
                continue
            canvas = QImage(width, height, QImage.Format.Format_RGB32)
            canvas.fill(QColor("#0E0C12"))
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            draw_wallpaper_mode(
                painter,
                source,
                width,
                height,
                self._wallpaper_mode_for_output(str(display.get("name", ""))),
            )
            painter.end()
            target = RENDERED_WALLPAPER_DIR / f"{sanitize_output_name(str(display.get('name', 'display')))}.png"
            canvas.save(str(target), "PNG")
            rendered_paths.append(target)
        return rendered_paths

    def _apply_wallpaper(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return
        self.wallpaper = path
        self._apply_current_wallpaper_layout()
        self._apply_matugen_palette()
        self.settings_state["appearance"]["wallpaper_mode"] = "picture"
        self.settings_state["appearance"]["slideshow_enabled"] = False
        self._slideshow_timer.stop()
        self._save_appearance_state()

    def _apply_random_wallpaper(self) -> None:
        folder = Path(self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            if hasattr(self, "appearance_status"):
                self.appearance_status.setText("No images found in the current slideshow folder.")
            return
        choice = random.choice(choices)
        self._apply_wallpaper(choice)

    def _choose_wallpaper_file(self) -> None:
        selected = run_text([
            "zenity",
            "--file-selection",
            "--title=Choose Wallpaper",
            "--file-filter=Images | *.png *.jpg *.jpeg *.webp *.bmp",
        ])
        if not selected:
            return
        self._apply_wallpaper(Path(selected).expanduser())

    def _choose_wallpaper_folder(self) -> None:
        selected = run_text(["zenity", "--file-selection", "--directory", "--title=Choose Slideshow Folder"])
        if not selected:
            return
        self.settings_state["appearance"]["slideshow_folder"] = str(Path(selected).expanduser())
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        save_settings_state(self.settings_state)
        if hasattr(self, "appearance_status"):
            self.appearance_status.setText(f"Slideshow folder updated to {Path(selected).expanduser()}.")

    def _set_slideshow_interval(self, value: int) -> None:
        self.settings_state["appearance"]["slideshow_interval"] = int(value)
        save_settings_state(self.settings_state)
        self._slideshow_timer.setInterval(int(value) * 1000)

    def _toggle_slideshow(self) -> None:
        if self._slideshow_timer.isActive():
            self._slideshow_timer.stop()
            self.settings_state["appearance"]["slideshow_enabled"] = False
            save_settings_state(self.settings_state)
            self._sync_wallpaper_controls()
            return
        folder = Path(self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            return
        self.settings_state["appearance"]["wallpaper_mode"] = "slideshow"
        self.settings_state["appearance"]["slideshow_enabled"] = True
        self._slideshow_timer.setInterval(max(5, int(self.settings_state["appearance"].get("slideshow_interval", 30))) * 1000)
        save_settings_state(self.settings_state)
        self._advance_slideshow()
        self._slideshow_timer.start()
        self._sync_wallpaper_controls()

    def _advance_slideshow(self) -> None:
        folder = Path(self.settings_state["appearance"].get("slideshow_folder", str(WALLS_DIR))).expanduser()
        choices = wallpaper_candidates(folder)
        if not choices:
            self._slideshow_timer.stop()
            self.settings_state["appearance"]["slideshow_enabled"] = False
            save_settings_state(self.settings_state)
            self._sync_wallpaper_controls()
            return
        self._slideshow_index = (self._slideshow_index + 1) % len(choices)
        self.wallpaper = choices[self._slideshow_index]
        self._apply_current_wallpaper_layout()
        self._apply_matugen_palette()
        self._save_appearance_state()

    def _save_home_assistant_settings(self) -> None:
        self.settings_state["home_assistant"]["url"] = normalize_ha_url(self.ha_url_input.text())
        self.settings_state["home_assistant"]["token"] = self.ha_token_input.text().strip()
        save_settings_state(self.settings_state)
        self.ha_status.setText("Home Assistant settings saved.")

    def _refresh_home_assistant_entities(self) -> None:
        payload, error_text = fetch_home_assistant_json(
            self.settings_state["home_assistant"].get("url", ""),
            self.settings_state["home_assistant"].get("token", ""),
            "/api/states",
        )
        if error_text or not isinstance(payload, list):
            self.ha_status.setText(error_text or "No entities available.")
            self._ha_entities = []
            self._ha_entity_map = {}
            self._rebuild_ha_entity_list()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        self._ha_entity_map = {str(item.get("entity_id", "")): item for item in self._ha_entities}
        self.ha_status.setText(f"Fetched {len(self._ha_entities)} entities successfully.")
        self._rebuild_ha_entity_list()

    def _rebuild_ha_entity_list(self) -> None:
        while self.ha_entity_layout.count():
            item = self.ha_entity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._ha_entities:
            empty = QLabel("No Home Assistant entities to display. Save credentials and fetch entities.")
            empty.setStyleSheet("color: rgba(246,235,247,0.62);")
            empty.setWordWrap(True)
            self.ha_entity_layout.addWidget(empty)
            self.ha_entity_layout.addStretch(1)
            return
        pinned = set(self.settings_state["home_assistant"].get("pinned_entities", []))
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            attrs = entity.get("attributes", {}) or {}
            name = str(attrs.get("friendly_name", entity_id))
            pin_button = QPushButton("Unpin" if entity_id in pinned else "Pin")
            pin_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            pin_button.clicked.connect(lambda checked=False, current=entity_id: self._toggle_pin_entity(current))
            row = SettingsRow(
                material_icon("widgets"),
                name,
                f"{entity_id} • {state}",
                self.icon_font,
                self.ui_font,
                pin_button,
            )
            self.ha_entity_layout.addWidget(row)
        self.ha_entity_layout.addStretch(1)

    def _toggle_pin_entity(self, entity_id: str) -> None:
        pinned = list(self.settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self.ha_status.setText("You can pin up to five entities.")
                return
            pinned.append(entity_id)
        self.settings_state["home_assistant"]["pinned_entities"] = pinned
        save_settings_state(self.settings_state)
        self.ha_status.setText(f"{len(pinned)}/5 entities pinned.")
        self._rebuild_ha_entity_list()

    def _save_ntfy_settings(self) -> None:
        ntfy = self.settings_state.setdefault("ntfy", {})
        ntfy["server_url"] = self.ntfy_server_input.text().strip().rstrip("/")
        ntfy["topic"] = self.ntfy_topic_input.text().strip()
        ntfy["token"] = self.ntfy_token_input.text().strip()
        ntfy["username"] = self.ntfy_username_input.text().strip()
        ntfy["password"] = self.ntfy_password_input.text()
        save_settings_state(self.settings_state)
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText("ntfy settings saved.")

    def _send_ntfy_test(self) -> None:
        self._save_ntfy_settings()
        ntfy = self.settings_state.get("ntfy", {})
        ok, message = send_ntfy_message(
            str(ntfy.get("server_url", "")),
            str(ntfy.get("topic", "")),
            "Hanauta Test",
            "ntfy integration is working.",
            token=str(ntfy.get("token", "")),
            username=str(ntfy.get("username", "")),
            password=str(ntfy.get("password", "")),
        )
        if hasattr(self, "ntfy_status"):
            self.ntfy_status.setText(message if message else ("ntfy test sent." if ok else "ntfy test failed."))

    def _refresh_system_overview(self) -> None:
        session = os.environ.get("XDG_SESSION_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "unknown"
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            screen_text = "Unavailable"
        else:
            geo = screen.geometry()
            screen_text = f"{geo.width()}x{geo.height()}"
        uptime_seconds = 0
        try:
            uptime_seconds = int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
        except Exception:
            uptime_seconds = 0
        values = {
            "Host": platform.node() or "unknown",
            "Kernel": platform.release() or "unknown",
            "Session": session,
            "Python": platform.python_version(),
            "Uptime": format_uptime(uptime_seconds),
            "Screen": screen_text,
        }
        for key, label in getattr(self, "system_overview_labels", {}).items():
            label.setText(values.get(key, "..."))

    def _current_picom_values(self) -> dict[str, object]:
        return {
            "backend": self.picom_backend_combo.currentText(),
            "vsync": self.picom_vsync_switch.isChecked(),
            "use-damage": self.picom_damage_switch.isChecked(),
            "shadow": self.picom_shadow_switch.isChecked(),
            "shadow-radius": self.picom_shadow_radius_slider.value(),
            "shadow-opacity": self.picom_shadow_opacity_slider.value() / 100.0,
            "shadow-offset-x": self.picom_shadow_offset_x_slider.value(),
            "shadow-offset-y": self.picom_shadow_offset_y_slider.value(),
            "fading": self.picom_fading_switch.isChecked(),
            "active-opacity": self.picom_active_opacity_slider.value() / 100.0,
            "inactive-opacity": self.picom_inactive_opacity_slider.value() / 100.0,
            "corner-radius": self.picom_corner_radius_slider.value(),
            "transparent-clipping": self.picom_clip_switch.isChecked(),
            "detect-rounded-corners": self.picom_rounded_switch.isChecked(),
        }

    def _apply_picom_settings(self) -> None:
        values = self._current_picom_values()
        text = update_picom_config(read_picom_text(), values)
        try:
            PICOM_CONFIG_FILE.write_text(text, encoding="utf-8")
        except Exception as exc:
            self.picom_status.setText(f"Unable to write picom.conf: {exc}")
            return
        self.picom_state = dict(values)
        self.picom_status.setText("picom.conf updated. Restart picom to apply immediately.")

    def _restart_picom(self) -> None:
        subprocess.run(["pkill", "-x", "picom"], capture_output=True, text=True, check=False)
        result = subprocess.run(
            ["picom", "--config", str(PICOM_CONFIG_FILE), "--daemon"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.picom_status.setText((result.stderr or result.stdout or "Unable to restart picom.").strip())
            return
        self.picom_status.setText("Picom restarted with the current configuration.")

    def _reset_picom_defaults(self) -> None:
        try:
            PICOM_CONFIG_FILE.write_text(PICOM_DEFAULT_CONFIG, encoding="utf-8")
        except Exception as exc:
            self.picom_status.setText(f"Unable to reset picom.conf: {exc}")
            return
        self.picom_state = parse_picom_settings(PICOM_DEFAULT_CONFIG)
        self._sync_picom_controls()
        self.picom_status.setText("picom.conf restored to the default profile.")

    def _sync_picom_controls(self) -> None:
        self.picom_backend_combo.setCurrentText(str(self.picom_state.get("backend", "glx")))
        for switch, value in (
            (self.picom_vsync_switch, bool(self.picom_state.get("vsync", True))),
            (self.picom_damage_switch, bool(self.picom_state.get("use-damage", True))),
            (self.picom_shadow_switch, bool(self.picom_state.get("shadow", True))),
            (self.picom_fading_switch, bool(self.picom_state.get("fading", False))),
            (self.picom_clip_switch, bool(self.picom_state.get("transparent-clipping", False))),
            (self.picom_rounded_switch, bool(self.picom_state.get("detect-rounded-corners", True))),
        ):
            switch.setChecked(value)
            switch._apply_state()
        for name, value in (
            ("picom_shadow_radius_slider", int(self.picom_state.get("shadow-radius", 18))),
            ("picom_shadow_opacity_slider", int(float(self.picom_state.get("shadow-opacity", 0.18)) * 100)),
            ("picom_shadow_offset_x_slider", int(self.picom_state.get("shadow-offset-x", -12))),
            ("picom_shadow_offset_y_slider", int(self.picom_state.get("shadow-offset-y", -12))),
            ("picom_active_opacity_slider", int(float(self.picom_state.get("active-opacity", 1.0)) * 100)),
            ("picom_inactive_opacity_slider", int(float(self.picom_state.get("inactive-opacity", 1.0)) * 100)),
            ("picom_corner_radius_slider", int(self.picom_state.get("corner-radius", 18))),
        ):
            slider = getattr(self, name, None)
            if isinstance(slider, QSlider):
                slider.setValue(value)

    def _center_rect(self) -> QRect:
        screen = QGuiApplication.primaryScreen() or self.screen()
        if screen is None:
            return QRect(0, 0, self.width(), self.height())
        available = screen.availableGeometry()
        x = available.x() + (available.width() - self.width()) // 2
        y = available.y() + (available.height() - self.height()) // 2
        return QRect(x, y, self.width(), self.height())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        target = self._center_rect()
        start = QRect(target.x(), target.y() + 24, int(target.width() * 0.96), int(target.height() * 0.96))
        self.setGeometry(start)
        QTimer.singleShot(80, self._apply_i3_window_rules)
        opacity = QPropertyAnimation(self, b"windowOpacity", self)
        opacity.setDuration(240)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        geometry = QPropertyAnimation(self, b"geometry", self)
        geometry.setDuration(320)
        geometry.setStartValue(start)
        geometry.setEndValue(target)
        geometry.setEasingCurve(QEasingCurve.Type.OutBack)
        self._window_animation = QParallelAnimationGroup(self)
        self._window_animation.addAnimation(opacity)
        self._window_animation.addAnimation(geometry)
        self._window_animation.start()

    def _apply_i3_window_rules(self) -> None:
        target = self._center_rect()
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="Hanauta Settings"]',
                    (
                        "floating enable, move position "
                        f"{target.x()} px {target.y()} px, "
                        f"resize set {target.width()} px {target.height()} px"
                    ),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def _apply_styles(self) -> None:
        theme = self.theme_palette
        accent = self.current_accent["accent"]
        soft = self.current_accent["soft"]
        shell_bg_end = theme.background if self.settings_state["appearance"].get("transparency", True) else theme.surface
        self.setStyleSheet(
            f"""
            QWidget#settingsWindow {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
            }}
            QFrame#shell {{
                background: {rgba(theme.surface_container, 0.94)};
                border: 1px solid {rgba(theme.outline, 0.20)};
                border-radius: 18px;
            }}
            QFrame#topHeader {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border-bottom: 1px solid {rgba(theme.outline, 0.16)};
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
            }}
            QFrame#sidebar {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QFrame#headerLeadChip, QFrame#sidebarNavSection {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
            }}
            QLabel#sidebarTitle {{
                color: {theme.text};
            }}
            QLabel#sidebarSectionLabel {{
                color: {theme.text_muted};
                padding-left: 8px;
                letter-spacing: 0.7px;
                text-transform: uppercase;
            }}
            QLabel#headerLeadIcon {{
                color: {accent};
                font-family: "{self.icon_font}";
            }}
            QLabel#headerLeadText {{
                color: {theme.text_muted};
            }}
            QLabel#headerTitle {{
                color: {theme.text};
            }}
            QLabel#headerSubtitle {{
                color: {theme.text_muted};
            }}
            QScrollArea#bodyScroll {{
                background: transparent;
            }}
            QWidget#content {{
                background: transparent;
            }}
            QPushButton[iconButton="true"] {{
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.icon};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
            }}
            QPushButton[iconButton="true"]:hover {{
                background: {theme.hover_bg};
                border-color: {rgba(theme.outline, 0.16)};
            }}
            QFrame#contentCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QFrame#appearanceCard {{
                background: {rgba(theme.surface_container, 0.92)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QLabel#appearanceTitle {{
                color: {theme.text};
            }}
            QLabel#appearanceSubtitle {{
                color: {theme.text_muted};
            }}
            QFrame#appearanceHeroWrap {{
                background: {rgba(theme.surface_container_high, 0.86)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QFrame#appearanceActionColumn, QFrame#appearanceAccentFrame {{
                background: {rgba(theme.surface_container_high, 0.86)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
            }}
            QLabel#appearanceSectionLabel {{
                color: {theme.primary};
                letter-spacing: 1px;
            }}
            QProgressBar#settingsProgressBar {{
                min-height: 8px;
                max-height: 8px;
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                background: {rgba(theme.surface_container_high, 0.82)};
            }}
            QProgressBar#settingsProgressBar::chunk {{
                border-radius: 999px;
                background: {theme.primary};
            }}
            QFrame#previewCard {{
                background: transparent;
                border: none;
            }}
            QPushButton#navPill {{
                min-height: 44px;
                border: 1px solid transparent;
                border-radius: 14px;
                background: transparent;
                color: {theme.text};
                text-align: left;
            }}
            QPushButton#navPill:hover {{
                background: {theme.hover_bg};
                border-color: {theme.chip_border};
            }}
            QPushButton#navPill:checked {{
                background: {soft};
                border-color: {theme.app_focused_border};
                color: {theme.text};
            }}
            QPushButton#navPill[compact="true"] {{
                min-height: 42px;
                max-width: 52px;
                padding: 0;
            }}
            QPushButton#navPill QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
            }}
            QPushButton#actionCard {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
                color: {theme.text};
                text-align: left;
            }}
            QPushButton#actionCard:hover {{
                background: {theme.hover_bg};
                border: 1px solid {theme.app_focused_border};
            }}
            QFrame#actionIconWrap, QFrame#rowIconWrap {{
                background: {theme.accent_soft};
                border: 1px solid {theme.app_focused_border};
                border-radius: 10px;
            }}
            QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
                color: {theme.primary};
            }}
            QPushButton#segmentedChip {{
                padding: 0 14px;
                min-height: 32px;
                border-radius: 999px;
                border: 1px solid {rgba(theme.outline, 0.16)};
                background: {rgba(theme.surface_container_high, 0.88)};
                color: {theme.text};
            }}
            QPushButton#segmentedChip:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#segmentedChip:checked {{
                background: {accent};
                color: {theme.active_text};
                border-color: {theme.app_focused_border};
            }}
            QPushButton#themeModeCard {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
                color: {theme.text};
            }}
            QPushButton#themeModeCard:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#themeModeCard:checked {{
                background: {accent};
                color: {theme.active_text};
                border-color: rgba(255,255,255,0.0);
            }}
            QPushButton#themeModeCard:checked QLabel {{
                color: {theme.active_text};
            }}
            QPushButton#themeModeCard QLabel[iconRole="true"] {{
                font-family: "{self.icon_font}";
            }}
            QFrame#settingsRow {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QFrame#serviceSection {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            QPushButton#serviceHeaderButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                text-align: left;
            }}
            QPushButton#serviceHeaderButton:hover {{
                background: {theme.hover_bg};
            }}
            QPushButton#serviceHeaderButton[serviceEnabled="false"] {{
                background: {theme.surface_container};
                border-color: {theme.chip_border};
            }}
            QLabel#serviceChevron {{
                color: {theme.icon};
                font-family: "{self.icon_font}";
            }}
            QComboBox#settingsCombo {{
                min-height: 38px;
                padding: 0 12px;
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
            }}
            QComboBox#settingsCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox#settingsCombo QAbstractItemView {{
                background: {theme.surface};
                color: {theme.text};
                border: 1px solid {theme.panel_border};
                selection-background-color: {theme.accent_soft};
            }}
            QLineEdit {{
                background: {theme.surface_container};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
                color: {theme.text};
                padding: 10px 12px;
                selection-background-color: {theme.accent_soft};
            }}
            QLineEdit:focus {{
                border-color: {theme.app_focused_border};
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton, QPushButton#dangerButton {{
                min-height: 38px;
                padding: 0 14px;
                border-radius: 14px;
                color: {theme.text};
            }}
            QPushButton#primaryButton {{
                background: {accent};
                color: {theme.active_text};
                border: none;
            }}
            QPushButton#secondaryButton {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
            }}
            QPushButton#dangerButton {{
                background: {theme.error};
                border: 1px solid {theme.error};
                color: {theme.on_error};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {theme.app_running_border};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {theme.text};
            }}
            QScrollBar:vertical {{
                width: 10px;
                background: transparent;
                margin: 8px 0 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.app_running_border};
                border-radius: 5px;
                min-height: 42px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--page", choices=("overview", "appearance", "display", "region", "bar", "services", "picom"), default="appearance")
    parser.add_argument("--service-section", default="")
    parser.add_argument("--ensure-settings", action="store_true")
    parser.add_argument("--restore-displays", action="store_true")
    parser.add_argument("--restore-wallpaper", action="store_true")
    parser.add_argument("--restore-vpn", action="store_true")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if args.ensure_settings:
        ensure_settings_state()
        return 0
    if args.restore_displays:
        restore_saved_displays()
        return 0
    if args.restore_wallpaper:
        restore_saved_wallpaper()
        return 0
    if args.restore_vpn:
        restore_saved_vpn()
        return 0
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda signum, frame: app.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)
    window = SettingsWindow(initial_page=args.page, initial_service_section=str(args.service_section or ""))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
