#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQt6 notification center rebuilt from idea.html.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib import error, parse, request

from PyQt6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCharFormat,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCalendarWidget,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import entry_command, entry_patterns, python_executable
from pyqt.shared.plugin_runtime import resolve_plugin_script
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family

ROOT = APP_DIR.parents[1]
SCRIPTS_DIR = ROOT / "hanauta" / "scripts"
FONTS_DIR = ROOT / "assets" / "fonts"
FALLBACK_COVER = ROOT / "assets" / "fallback.webp"
ASSETS_DIR = APP_DIR / "assets"
BIN_DIR = ROOT / "bin"
HOME_ASSISTANT_ICON = ASSETS_DIR / "home-assistant-dark.svg"
KDECONNECT_ICON = ASSETS_DIR / "kdeconnect.svg"
STEAM_ICON = ASSETS_DIR / "steam-logo.svg"
LUTRIS_ICON = ASSETS_DIR / "lutris-logo.svg"
def _preferred_icon_path(asset_name: str, system_path: str) -> str:
    local_icon = ASSETS_DIR / asset_name
    if local_icon.exists():
        return str(local_icon)
    return system_path


WIFI_NOTIFICATION_ICON = _preferred_icon_path(
    "network-wireless-connected-100.svg",
    "/usr/share/icons/Papirus-Dark/24x24/panel/network-wireless-connected-100.svg",
)
BLUETOOTH_NOTIFICATION_ICON = _preferred_icon_path(
    "bluetooth-active.svg",
    "/usr/share/icons/Papirus-Dark/24x24/panel/bluetooth-active.svg",
)
AIRPLANE_NOTIFICATION_ICON = _preferred_icon_path(
    "airplane-mode-on.svg",
    "/usr/share/icons/Papirus-Dark/24x24/panel/airplane-mode-on.svg",
)
CAFFEINE_NOTIFICATION_ICON = _preferred_icon_path("caffeine.svg", "coffee")
NIGHT_LIGHT_NOTIFICATION_ICON = _preferred_icon_path("night-light.svg", "nightlight")
CALENDAR_NOTIFICATION_ICON = _preferred_icon_path(
    "calendar_today.svg", "x-office-calendar"
)
WEATHER_HISTORY_ICON = (
    ASSETS_DIR / "weather-icons" / "monochrome" / "svg-static" / "overcast.svg"
)
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "notification-center"
SETTINGS_FILE = STATE_DIR / "settings.json"
SERVICE_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "service"
CALENDAR_EVENTS_CACHE = SERVICE_STATE_DIR / "calendar_events.json"
NOTIFICATION_HISTORY_FILE = (
    Path.home()
    / ".local"
    / "state"
    / "hanauta"
    / "notification-daemon"
    / "history.json"
)
def _resolve_qcal_wrapper_script() -> Path | None:
    resolved = resolve_plugin_script("qcal-wrapper.py", ["calendar"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-calendar" / "qcal-wrapper.py",
        Path.home() / "dev" / "hanauta-plugin-calendar" / "qcal-wrapper.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


QCAL_WRAPPER = _resolve_qcal_wrapper_script() or Path()
LUTRIS_DB = Path.home() / ".local" / "share" / "lutris" / "pga.db"
LUTRIS_COVERART_DIR = Path.home() / ".local" / "share" / "lutris" / "coverart"
SETTINGS_PAGE_SCRIPT = APP_DIR / "pyqt" / "settings-page" / "settings.py"
VPN_CONTROL_SCRIPT = (
    resolve_plugin_script("vpn_control.py", ["vpn-control", "vpn"]) or Path()
)
CHRISTIAN_WIDGET_SCRIPT = (
    resolve_plugin_script("christian_widget.py", ["religion-christian", "christian"])
    or Path()
)
REMINDERS_WIDGET_SCRIPT = (
    resolve_plugin_script("reminders_widget.py", ["reminders"]) or Path()
)
POMODORO_WIDGET_SCRIPT = (
    resolve_plugin_script("pomodoro_widget.py", ["pomodoro"]) or Path()
)
RSS_WIDGET_SCRIPT = resolve_plugin_script("rss_widget.py", ["rss"]) or Path()
OBS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("obs_widget.py", ["obs"])
CRYPTO_WIDGET_SCRIPT: Path | None = resolve_plugin_script(
    "crypto_widget.py", ["crypto"]
)
VPS_WIDGET_SCRIPT: Path | None = resolve_plugin_script("vps_widget.py", ["vps"])


def _resolve_desktop_clock_widget_script() -> Path | None:
    resolved = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        ROOT / "hanauta" / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


DESKTOP_CLOCK_WIDGET_SCRIPT: Path | None = _resolve_desktop_clock_widget_script()
DESKTOP_CLOCK_BINARY = ROOT / "bin" / "hanauta-clock"
GAME_MODE_POPUP_SCRIPT: Path | None = resolve_plugin_script(
    "game_mode_popup.py", ["game-mode", "gamemode"]
)
POWERMENU_SCRIPT = APP_DIR / "pyqt" / "powermenu" / "powermenu.py"
PROFILE_PHOTO_CANDIDATES = [Path.home() / ".face.png", Path.home() / ".face.jpg"]

MATERIAL_ICONS = {
    "airplanemode_active": "\ue195",
    "arrow_back": "\ue5c4",
    "bluetooth": "\ue1a7",
    "brightness_medium": "\ue1ae",
    "camera_alt": "\ue3b0",
    "calendar_today": "\ue935",
    "check_circle": "\ue86c",
    "chevron_left": "\ue5cb",
    "chevron_right": "\ue5cc",
    "content_paste": "\ue14f",
    "close": "\ue5cd",
    "coffee": "\uefef",
    "delete_sweep": "\ue16c",
    "do_not_disturb_on": "\ue644",
    "home": "\ue88a",
    "hub": "\uee20",
    "invert_colors": "\ue891",
    "lightbulb": "\ue0f0",
    "nightlight": "\uf03d",
    "pause": "\ue034",
    "person": "\ue7fd",
    "phone_android": "\ue324",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "smartphone": "\ue32c",
    "save": "\ue161",
    "settings": "\ue8b8",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "thermostat": "\ue1ff",
    "tune": "\ue429",
    "volume_up": "\ue050",
    "wifi": "\ue63e",
    "lock": "\ue897",
    "auto_awesome": "\ue65f",
    "timer": "\ue425",
    "public": "\ue80b",
    "videocam": "\ue04b",
    "show_chart": "\ue6e1",
    "storage": "\ue1db",
    "watch": "\ue334",
    "sports_esports": "\uea28",
}

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
        "enabled": True,
        "show_in_notification_center": True,
    },
    "crypto_widget": {
        "enabled": True,
        "show_in_notification_center": True,
    },
    "vps_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
    "desktop_clock_widget": {
        "enabled": False,
        "show_in_notification_center": True,
    },
    "game_mode": {
        "enabled": False,
        "show_in_notification_center": True,
        "show_in_bar": False,
    },
}


def run_cmd(cmd: list[str], timeout: float = 2.0) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_script(script_name: str, *args: str) -> str:
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return ""
    return run_cmd([str(path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    path = SCRIPTS_DIR / script_name
    if not path.exists():
        return
    try:
        subprocess.Popen(
            [str(path), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def apply_antialias_font(widget: QWidget) -> None:
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)


def terminate_background_matches(pattern: str) -> None:
    try:
        subprocess.run(
            ["pkill", "-f", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def run_bg_singleton(script_path: Path, *args: str) -> None:
    command = entry_command(script_path, *args)
    if not command:
        return
    for pattern in entry_patterns(script_path):
        terminate_background_matches(pattern)
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def desktop_clock_command() -> list[str]:
    if DESKTOP_CLOCK_WIDGET_SCRIPT is not None and DESKTOP_CLOCK_WIDGET_SCRIPT.exists():
        return entry_command(DESKTOP_CLOCK_WIDGET_SCRIPT)
    if DESKTOP_CLOCK_BINARY.exists():
        return [str(DESKTOP_CLOCK_BINARY)]
    return []


def notification_control_command(*args: str) -> list[str]:
    local = BIN_DIR / "hanauta-notifyctl"
    if local.exists():
        return [str(local), *args]
    return ["hanauta-notifyctl", *args]


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
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


def format_millis(ms: int) -> str:
    ms = max(0, ms)
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def merged_service_settings(payload: object) -> dict[str, dict[str, bool]]:
    services = payload if isinstance(payload, dict) else {}
    merged: dict[str, dict[str, bool]] = {}
    for key, defaults in DEFAULT_SERVICE_SETTINGS.items():
        current = services.get(key, {}) if isinstance(services, dict) else {}
        if not isinstance(current, dict):
            current = {}
        merged[key] = {
            "enabled": bool(current.get("enabled", defaults["enabled"])),
            "show_in_notification_center": bool(
                current.get(
                    "show_in_notification_center",
                    defaults["show_in_notification_center"],
                )
            ),
        }
        if key == "kdeconnect":
            merged[key]["low_battery_fullscreen_notification"] = bool(
                current.get(
                    "low_battery_fullscreen_notification",
                    defaults.get("low_battery_fullscreen_notification", False),
                )
            )
            try:
                merged[key]["low_battery_threshold"] = max(
                    1,
                    min(
                        100,
                        int(
                            current.get(
                                "low_battery_threshold",
                                defaults.get("low_battery_threshold", 20),
                            )
                        ),
                    ),
                )
            except Exception:
                merged[key]["low_battery_threshold"] = int(
                    defaults.get("low_battery_threshold", 20)
                )
        elif key == "christian_widget":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
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
        elif key == "home_assistant":
            merged[key]["show_in_bar"] = bool(
                current.get("show_in_bar", defaults.get("show_in_bar", False))
            )
    return merged


def load_notification_settings() -> dict:
    default = {
        "appearance": {"accent": "orchid"},
        "home_assistant": {"url": "", "token": "", "pinned_entities": []},
        "services": merged_service_settings({}),
        "display": {"layout_mode": "extend", "primary": "", "outputs": []},
        "autolock": {"enabled": True, "timeout_minutes": 2},
        "weather": {
            "enabled": False,
            "name": "",
            "admin1": "",
            "country": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "timezone": "auto",
        },
        "ntfy": {
            "enabled": False,
            "show_in_bar": False,
            "server_url": "https://ntfy.sh",
            "topic": "",
            "token": "",
            "username": "",
            "password": "",
            "auth_mode": "token",
            "topics": [],
            "all_topics": False,
            "hide_notification_content": False,
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
    pinned = [
        item
        for item in home_assistant.get("pinned_entities", [])
        if isinstance(item, str)
    ][:5]
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
        autolock["timeout_minutes"] = max(
            1, min(60, int(autolock.get("timeout_minutes", 2)))
        )
    except Exception:
        autolock["timeout_minutes"] = 2
    weather = dict(payload.get("weather", {}))
    weather.setdefault("enabled", False)
    weather.setdefault("name", "")
    weather.setdefault("admin1", "")
    weather.setdefault("country", "")
    weather.setdefault("latitude", 0.0)
    weather.setdefault("longitude", 0.0)
    weather.setdefault("timezone", "auto")
    ntfy = dict(payload.get("ntfy", {}))
    ntfy.setdefault("enabled", False)
    ntfy.setdefault("show_in_bar", False)
    ntfy.setdefault("server_url", "https://ntfy.sh")
    ntfy.setdefault("topic", "")
    ntfy.setdefault("token", "")
    ntfy.setdefault("username", "")
    ntfy.setdefault("password", "")
    ntfy.setdefault("auth_mode", "token")
    ntfy.setdefault("topics", [])
    ntfy.setdefault("all_topics", False)
    ntfy["hide_notification_content"] = bool(
        ntfy.get("hide_notification_content", False)
    )
    topics = [
        str(item).strip()
        for item in ntfy.get("topics", [])
        if isinstance(item, str) and str(item).strip()
    ]
    ntfy["topics"] = topics
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


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f"{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(payload, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def tinted_svg_pixmap(path: Path, color: QColor, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return pixmap


def render_svg_pixmap(path: Path, size: int = 18) -> QPixmap:
    if not path.exists():
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def render_theme_icon_pixmap(names: list[str], size: int = 18) -> QPixmap:
    for name in names:
        if not name:
            continue
        icon = QIcon.fromTheme(name)
        if icon.isNull():
            continue
        pixmap = icon.pixmap(size, size)
        if not pixmap.isNull():
            return pixmap
    return QPixmap()


def accent_palette(name: str) -> dict[str, str]:
    palettes = {
        "orchid": {
            "accent": "#D0BCFF",
            "on_accent": "#381E72",
            "soft": "rgba(208,188,255,0.18)",
        },
        "mint": {
            "accent": "#8FE3CF",
            "on_accent": "#11352D",
            "soft": "rgba(143,227,207,0.18)",
        },
        "sunset": {
            "accent": "#FFB59E",
            "on_accent": "#4D2418",
            "soft": "rgba(255,181,158,0.18)",
        },
    }
    return palettes.get(name, palettes["orchid"])


def normalize_ha_url(url: str) -> str:
    return url.strip().rstrip("/")


def fetch_home_assistant_json(
    base_url: str, token: str, path: str
) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=3.5) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def post_home_assistant_json(
    base_url: str, token: str, path: str, payload: dict
) -> tuple[object | None, str]:
    if not base_url or not token:
        return None, "Home Assistant URL and token are required."
    data = json.dumps(payload).encode("utf-8")
    try:
        req = request.Request(
            f"{normalize_ha_url(base_url)}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=3.5) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else None), ""
    except error.HTTPError as exc:
        return None, f"Home Assistant returned HTTP {exc.code}."
    except Exception:
        return None, "Unable to reach Home Assistant."


def load_notification_history(limit: int = 3) -> list[dict]:
    def _decode_octal_runs(raw_text: str) -> str:
        pattern = re.compile(r"(?:\\[0-7]{3})+")

        def _replace(match: re.Match[str]) -> str:
            run = match.group(0)
            octets = re.findall(r"\\([0-7]{3})", run)
            data = bytes(int(value, 8) for value in octets)
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("latin-1", errors="replace")

        return pattern.sub(_replace, raw_text)

    def _load_payload() -> object:
        try:
            raw = NOTIFICATION_HISTORY_FILE.read_text(encoding="utf-8")
        except Exception:
            return None
        try:
            return json.loads(raw)
        except Exception:
            try:
                return json.loads(_decode_octal_runs(raw))
            except Exception:
                return None

    def _value(raw_value: object) -> object:
        if isinstance(raw_value, dict):
            for key in ("data", "value", "id"):
                if key in raw_value:
                    return raw_value.get(key)
        return raw_value

    try:
        payload = _load_payload()
    except Exception:
        payload = None
    history: list[dict] = []
    if isinstance(payload, list):
        history = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        if payload.get("summary") or payload.get("body"):
            history.append(
                {
                    "id": payload.get("id", 0),
                    "app_name": str(payload.get("app_name", "")),
                    "summary": str(payload.get("summary", "")),
                    "body": str(payload.get("body", "")),
                    "icon": str(payload.get("icon", "")),
                    "desktop_entry": str(payload.get("desktop_entry", "")),
                    "timestamp": payload.get("timestamp", 0),
                }
            )
        raw = payload.get("data", [])
        if isinstance(raw, list) and raw and isinstance(raw[0], list):
            for item in raw[0]:
                if not isinstance(item, dict):
                    continue
                history.append(
                    {
                        "id": _value(item.get("id", 0)),
                        "app_name": str(
                            _value(item.get("app_name", item.get("appname", ""))) or ""
                        ),
                        "summary": str(_value(item.get("summary", "")) or ""),
                        "body": str(_value(item.get("body", "")) or ""),
                        "icon": str(
                            _value(item.get("app_icon", item.get("icon", ""))) or ""
                        ),
                        "desktop_entry": str(
                            _value(item.get("desktop_entry", "")) or ""
                        ),
                        "timestamp": _value(item.get("timestamp", 0)),
                    }
                )
    history = [item for item in history if item.get("summary") or item.get("body")]
    history.reverse()
    return history[:limit]


def resolve_rss_widget_script(settings_state: dict | None = None) -> Path:
    if RSS_WIDGET_SCRIPT.exists():
        return RSS_WIDGET_SCRIPT
    state = settings_state if isinstance(settings_state, dict) else {}
    marketplace = state.get("marketplace", {}) if isinstance(state, dict) else {}
    installed = (
        marketplace.get("installed_plugins", [])
        if isinstance(marketplace, dict)
        else []
    )
    if isinstance(installed, list):
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            if plugin_id != "rss_widget":
                continue
            install_path = str(row.get("install_path", "")).strip()
            if not install_path:
                continue
            candidate = Path(install_path).expanduser() / "rss_widget.py"
            if candidate.exists():
                return candidate
    return RSS_WIDGET_SCRIPT


def load_calendar_events(limit: int = 2) -> list[dict]:
    try:
        if CALENDAR_EVENTS_CACHE.exists():
            payload = json.loads(CALENDAR_EVENTS_CACHE.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                events = payload.get("events", [])
                if isinstance(events, list) and events:
                    return [item for item in events if isinstance(item, dict)][:limit]
                err = str(payload.get("error", "")).strip()
                if err:
                    return [
                        {
                            "title": "Calendar sync error",
                            "location": "Open Settings → Services → Calendar",
                            "start": err,
                            "source": "calendar",
                        }
                    ][:limit]
    except Exception:
        pass
    if not QCAL_WRAPPER.exists():
        return []
    try:
        result = subprocess.run(
            [
                python_executable(),
                str(QCAL_WRAPPER),
                "list",
                "--days",
                "14",
                "--limit",
                str(max(1, int(limit))),
            ],
            capture_output=True,
            text=True,
            timeout=20.0,
            check=False,
        )
        payload = json.loads(result.stdout or "{}")
    except Exception as exc:
        return [
            {
                "title": "Calendar sync error",
                "location": "Open Settings → Services → Calendar",
                "start": str(exc).strip() or "Unable to fetch events.",
                "source": "calendar",
            }
        ][:limit]
    if isinstance(payload, dict):
        events = payload.get("events", [])
        if isinstance(events, list) and events:
            return [item for item in events if isinstance(item, dict)][:limit]
        err = str(payload.get("error", "")).strip()
        if err:
            return [
                {
                    "title": "Calendar sync error",
                    "location": "Open Settings → Services → Calendar",
                    "start": err,
                    "source": "calendar",
                }
            ][:limit]
    events = payload.get("events", []) if isinstance(payload, dict) else []
    if not isinstance(events, list):
        return []
    return [item for item in events if isinstance(item, dict)][:limit]


def format_playtime_hours(hours: float) -> str:
    if hours <= 0:
        return "0m total"
    whole_hours = int(hours)
    minutes = int(round((hours - whole_hours) * 60))
    if whole_hours <= 0:
        return f"{minutes}m total"
    if minutes <= 0:
        return f"{whole_hours}h total"
    return f"{whole_hours}h {minutes}m total"


def load_lutris_game_slides(limit: int = 2) -> list[dict]:
    if not LUTRIS_DB.exists():
        return []
    try:
        connection = sqlite3.connect(LUTRIS_DB)
        cursor = connection.cursor()
        rows = list(
            cursor.execute(
                """
                SELECT name, slug, playtime, lastplayed, runner, platform
                FROM games
                WHERE installed = 1
                ORDER BY lastplayed DESC, playtime DESC
                LIMIT ?
                """,
                (limit,),
            )
        )
    except Exception:
        rows = []
    finally:
        try:
            connection.close()
        except Exception:
            pass
    slides: list[dict] = []
    for name, slug, playtime, lastplayed, runner, platform in rows:
        hours = float(playtime or 0.0)
        platform_label = f"Lutris • {runner or platform or 'Library'}"
        cover_path = LUTRIS_COVERART_DIR / f"{slug}.jpg" if slug else Path()
        if not cover_path.exists() and slug:
            png_path = LUTRIS_COVERART_DIR / f"{slug}.png"
            cover_path = png_path if png_path.exists() else Path()
        slides.append(
            {
                "title": str(name or "Lutris game"),
                "stats": [
                    format_playtime_hours(hours),
                    str(platform or runner or "Installed"),
                ],
                "logo": LUTRIS_ICON,
                "platform": platform_label,
                "accent": "primary",
                "playtime_hours": hours,
                "cover": cover_path,
            }
        )
    return slides


def _candidate_steam_roots() -> list[Path]:
    roots = [
        Path.home() / ".steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home()
        / ".var"
        / "app"
        / "com.valvesoftware.Steam"
        / ".local"
        / "share"
        / "Steam",
        Path.home() / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
    ]
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _steam_localconfig_paths() -> list[Path]:
    results: list[Path] = []
    for root in _candidate_steam_roots():
        if not root.exists():
            continue
        results.extend(root.glob("userdata/*/config/localconfig.vdf"))
    return results


def load_steam_game_slides(limit: int = 2) -> list[dict]:
    app_pattern = re.compile(
        r'"(\d+)"\s*\{[^{}]*?"name"\s*"([^"]+)"[^{}]*?"Playtime"\s*"(\d+)"', re.DOTALL
    )
    slides: list[dict] = []
    for config_path in _steam_localconfig_paths():
        try:
            raw = config_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for appid, name, minutes_text in app_pattern.findall(raw):
            minutes = int(minutes_text or "0")
            if minutes <= 0:
                continue
            hours = minutes / 60.0
            slides.append(
                {
                    "title": name,
                    "stats": [
                        format_playtime_hours(hours),
                        f"App {appid}",
                    ],
                    "logo": STEAM_ICON,
                    "platform": "Steam library",
                    "accent": "secondary",
                    "playtime_hours": hours,
                    "cover": Path(),
                }
            )
        if slides:
            break
    slides.sort(key=lambda item: float(item.get("playtime_hours", 0.0)), reverse=True)
    return slides[:limit]


class QuickSettingButton(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback):
        super().__init__()
        self.material_font = material_font
        self.title = title
        self.callback = callback
        self.theme = None
        self.accent = "#D0BCFF"
        self.on_accent = "#381E72"
        self.active = False
        self._icon_text = icon
        self._subtitle = "Off"
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("quickTile")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setFont(QFont(self.material_font, 18))
        self.icon_label.setObjectName("quickTileIcon")

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("quickTileTitle")
        self.subtitle_label = QLabel("Off")
        self.subtitle_label.setObjectName("quickTileSubtitle")
        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        text_wrap.addWidget(self.title_label)
        text_wrap.addWidget(self.subtitle_label)

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_wrap, 1)
        self._render()

    def apply_theme(self, theme, accent: str, on_accent: str) -> None:
        self.theme = theme
        self.accent = accent
        self.on_accent = on_accent
        self._render()

    def set_state(self, active: bool, icon: str, subtitle: str) -> None:
        self.active = active
        self._icon_text = icon
        self._subtitle = subtitle
        self._render()

    def _render(self) -> None:
        theme = self.theme
        if theme is not None:
            icon_color = self.on_accent if self.active else theme.icon
            title_color = self.on_accent if self.active else theme.text
            sub_color = rgba(self.on_accent, 0.78) if self.active else theme.text_muted
            bg = self.accent if self.active else theme.app_running_bg
            hover = theme.accent_soft if self.active else theme.hover_bg
        else:
            icon_color = "#381E72" if self.active else "rgba(255,255,255,0.82)"
            title_color = "#381E72" if self.active else "#ffffff"
            sub_color = (
                "rgba(56,30,114,0.78)" if self.active else "rgba(255,255,255,0.54)"
            )
            bg = "#D0BCFF" if self.active else "rgba(255,255,255,0.05)"
            hover = "#ddcbff" if self.active else "rgba(255,255,255,0.10)"
        self.setStyleSheet(
            f"""
            QFrame#quickTile {{
                background: {bg};
                border: none;
                border-radius: 18px;
            }}
            QFrame#quickTile:hover {{
                background: {hover};
            }}
            """
        )
        self.icon_label.setText(material_icon(self._icon_text))
        self.icon_label.setStyleSheet(f"color: {icon_color};")
        self.title_label.setText(self.title)
        self.title_label.setStyleSheet(f"color: {title_color}; font-weight: 600;")
        self.subtitle_label.setText(self._subtitle)
        self.subtitle_label.setStyleSheet(f"color: {sub_color}; font-size: 10px;")

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SidebarItemButton(QPushButton):
    def __init__(self, material_font: str, key: str, title: str, icon: str) -> None:
        super().__init__()
        self.key = key
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("sidebarItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("sidebarItemIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.text_label = QLabel(title)
        self.text_label.setObjectName("sidebarItemText")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1)
        self.apply_state(False, "#D0BCFF", "#381E72")

    def apply_state(
        self, active: bool, accent: str, on_accent: str, theme=None
    ) -> None:
        self.setChecked(active)
        if active:
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {accent};
                    border: none;
                    border-radius: 16px;
                }}
                QLabel#sidebarItemIcon, QLabel#sidebarItemText {{
                    color: {on_accent};
                    font-weight: 600;
                }}
                """
            )
        else:
            inactive_bg = (
                theme.app_running_bg if theme is not None else "rgba(255,255,255,0.04)"
            )
            hover_bg = theme.hover_bg if theme is not None else "rgba(255,255,255,0.08)"
            icon_color = theme.icon if theme is not None else "rgba(255,255,255,0.80)"
            text_color = theme.text if theme is not None else "rgba(255,255,255,0.90)"
            self.setStyleSheet(
                f"""
                QPushButton#sidebarItem {{
                    background: {inactive_bg};
                    border: none;
                    border-radius: 16px;
                }}
                QPushButton#sidebarItem:hover {{
                    background: {hover_bg};
                }}
                QLabel#sidebarItemIcon {{
                    color: {icon_color};
                }}
                QLabel#sidebarItemText {{
                    color: {text_color};
                    font-weight: 500;
                }}
                """
            )


class ActionTile(QFrame):
    def __init__(self, material_font: str, title: str, icon: str, callback) -> None:
        super().__init__()
        self.callback = callback
        self.setObjectName("actionTile")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self.icon_label = QLabel(material_icon(icon))
        self.icon_label.setObjectName("actionTileIcon")
        self.icon_label.setFont(QFont(material_font, 18))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("actionTileTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("actionTileSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

    def set_content(self, icon: str, title: str, subtitle: str) -> None:
        self.icon_label.setText(material_icon(icon))
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CompactIconAction(QPushButton):
    def __init__(self, material_font: str, icon: str) -> None:
        super().__init__(material_icon(icon))
        self.setObjectName("compactIconAction")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFont(QFont(material_font, 17))
        self.setFixedSize(34, 34)
        self.setProperty("active", False)

    def set_icon(self, icon: str) -> None:
        self.setText(material_icon(icon))

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class ServiceLauncherCard(QFrame):
    def __init__(
        self,
        material_font: str,
        title: str,
        detail: str,
        icon: str,
        action_label: str,
        callback,
    ) -> None:
        super().__init__()
        self.callback = callback
        self.setObjectName("infoCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sectionIcon")
        icon_label.setFixedWidth(20)
        icon_label.setFont(QFont(material_font, 18))

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("metricValue")
        subtitle_label = QLabel(detail)
        subtitle_label.setObjectName("statusHint")
        subtitle_label.setWordWrap(True)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        subtitle_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        text.addWidget(title_label)
        text.addWidget(subtitle_label)

        action = QPushButton(action_label)
        action.setObjectName("softButton")
        action.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        action.clicked.connect(callback)

        layout.addWidget(icon_label)
        layout.addLayout(text, 1)
        layout.addWidget(action)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self._full_text = text

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text
        self._apply_elision()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        metrics = self.fontMetrics()
        available = max(0, self.width() - 2)
        if available < 10:
            available = 100
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, available
        )
        super().setText(elided)


class ClickableLabel(QLabel):
    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class GameCarouselCard(QFrame):
    def __init__(self, ui_font: str, material_font: str) -> None:
        super().__init__()
        self.ui_font = ui_font
        self.material_font = material_font
        self.setObjectName("gameCarouselCard")
        self._slides: list[QFrame] = []
        self._dots: list[QLabel] = []
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(5000)
        self._auto_timer.timeout.connect(self.next_slide)
        self._auto_timer.start()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.kicker = QLabel("Recently games played")
        self.kicker.setObjectName("gameKicker")
        header.addWidget(self.kicker, 1)

        self.prev_button = QPushButton(material_icon("chevron_left"))
        self.prev_button.setObjectName("compactIconAction")
        self.prev_button.setFont(QFont(self.material_font, 17))
        self.prev_button.setFixedSize(30, 30)
        self.prev_button.clicked.connect(self.previous_slide)
        self.next_button = QPushButton(material_icon("chevron_right"))
        self.next_button.setObjectName("compactIconAction")
        self.next_button.setFont(QFont(self.material_font, 17))
        self.next_button.setFixedSize(30, 30)
        self.next_button.clicked.connect(self.next_slide)
        self.prev_button.clicked.connect(self._restart_autoplay)
        self.next_button.clicked.connect(self._restart_autoplay)
        header.addWidget(self.prev_button)
        header.addWidget(self.next_button)
        layout.addLayout(header)

        self.stack = QStackedWidget()
        self.stack.setObjectName("gameStack")
        layout.addWidget(self.stack)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(4)
        self.caption = QLabel("")
        self.caption.setObjectName("gameCaption")
        footer.addWidget(self.caption, 1)
        self.dots_wrap = QHBoxLayout()
        self.dots_wrap.setContentsMargins(0, 0, 0, 0)
        self.dots_wrap.setSpacing(4)
        footer.addLayout(self.dots_wrap)
        layout.addLayout(footer)

    def _cover_pixmap(self, path: Path, width: int = 74, height: int = 92) -> QPixmap:
        fallback = QPixmap(width, height)
        fallback.fill(Qt.GlobalColor.transparent)
        if not path.exists():
            return fallback
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return fallback
        scaled = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)
        rounded = QPixmap(width, height)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0.0, 0.0, float(width), float(height), 18.0, 18.0)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    def add_slide(
        self,
        title: str,
        stats: list[str],
        logo_path: Path,
        platform: str,
        accent: str,
        cover_path: Path | None = None,
    ) -> None:
        slide = QFrame()
        slide.setObjectName("gameSlideInner")
        slide.setProperty("accentColor", accent)
        slide_layout = QVBoxLayout(slide)
        slide_layout.setContentsMargins(0, 0, 0, 0)
        slide_layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        cover = QLabel()
        cover.setObjectName("gameCover")
        cover.setFixedSize(74, 92)
        cover.setPixmap(self._cover_pixmap(cover_path or Path()))
        top.addWidget(cover, 0, Qt.AlignmentFlag.AlignTop)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("gameSlideTitle")
        platform_label = QLabel(platform)
        platform_label.setObjectName("gameSlidePlatform")
        title_wrap.addWidget(title_label)
        title_wrap.addWidget(platform_label)
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(6)
        stat_values = stats or ["No telemetry yet"]
        for idx, text in enumerate(stat_values):
            stat = QLabel(text)
            stat.setObjectName("gameStatChip" if idx == 0 else "gameStatLabel")
            chip_row.addWidget(stat)
        chip_row.addStretch(1)
        title_wrap.addLayout(chip_row)
        top.addLayout(title_wrap, 1)
        slide_layout.addLayout(top)
        slide_layout.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(6)
        hint = QLabel("Last played across your launchers")
        hint.setObjectName("gameSlideHint")
        bottom.addWidget(hint, 1, Qt.AlignmentFlag.AlignBottom)
        logo = QLabel()
        logo.setObjectName("gamePlatformLogo")
        logo.setPixmap(render_svg_pixmap(logo_path, 22))
        bottom.addWidget(
            logo, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        )
        slide_layout.addLayout(bottom)

        self.stack.addWidget(slide)
        self._slides.append(slide)
        dot = QLabel("•")
        dot.setObjectName("carouselDot")
        self._dots.append(dot)
        self.dots_wrap.addWidget(dot)
        self._refresh_state()

    def clear_slides(self) -> None:
        # Removes all slide widgets and dots so we can repopulate asynchronously.
        for widget in list(getattr(self, "_slides", [])):
            try:
                self.stack.removeWidget(widget)
            except Exception:
                pass
            try:
                widget.deleteLater()
            except Exception:
                pass
        self._slides = []
        for dot in list(getattr(self, "_dots", [])):
            try:
                dot.deleteLater()
            except Exception:
                pass
        self._dots = []
        try:
            self.caption.setText("0/0")
        except Exception:
            pass
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _refresh_state(self) -> None:
        index = self.stack.currentIndex()
        if index < 0:
            return
        for offset, dot in enumerate(self._dots):
            dot.setProperty("active", offset == index)
            dot.style().unpolish(dot)
            dot.style().polish(dot)
        self.caption.setText(f"{index + 1}/{max(1, self.stack.count())}")
        self.prev_button.setEnabled(self.stack.count() > 1)
        self.next_button.setEnabled(self.stack.count() > 1)

    def next_slide(self) -> None:
        if self.stack.count() < 2:
            return
        self.stack.setCurrentIndex((self.stack.currentIndex() + 1) % self.stack.count())
        self._refresh_state()

    def previous_slide(self) -> None:
        if self.stack.count() < 2:
            return
        self.stack.setCurrentIndex((self.stack.currentIndex() - 1) % self.stack.count())
        self._refresh_state()

    def _restart_autoplay(self) -> None:
        if self.stack.count() < 2:
            return
        self._auto_timer.start()


class NotificationCenter(QWidget):
    calendarEventsReady = pyqtSignal(list)
    gameSlidesReady = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self.loaded_fonts = load_app_fonts()
        self.material_font = detect_font(
            self.loaded_fonts.get("material_icons", ""),
            self.loaded_fonts.get("material_icons_outlined", ""),
            self.loaded_fonts.get("material_symbols_outlined", ""),
            self.loaded_fonts.get("material_symbols_rounded", ""),
            "Material Icons",
            "Material Icons Outlined",
            "Material Symbols Outlined",
            "Material Symbols Rounded",
        )
        self.ui_font = detect_font(
            theme_font_family("ui"),
            "Rubik",
            self.loaded_fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
        self.mono_font = detect_font(
            theme_font_family("mono"),
            "JetBrains Mono",
            "JetBrainsMono Nerd Font",
            "DejaVu Sans Mono",
        )
        self._panel_animation: QPropertyAnimation | None = None
        self._syncing_sliders = False
        self._pending_brightness = 0
        self._pending_volume = 0
        self._media_player = ""
        self._media_duration_ms = 0
        self._media_position_ms = 0
        self._media_status = "Stopped"
        self._media_track_key = ""
        self._media_last_sync = monotonic()
        self._media_estimated_progress = False
        self._media_url = ""
        self._media_duration_cache: dict[str, int] = {}
        self._media_duration_pending: set[str] = set()
        self._calendar_events: list[dict] = []
        self._calendar_last_error = ""
        self._calendar_fetch_in_progress = False
        self._calendar_last_fetch = 0.0
        self._calendar_render_signature = ""
        self._notification_history: list[dict] = []
        self.settings_state = load_notification_settings()
        self.theme_palette = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.current_accent = accent_palette(
            self.settings_state["appearance"].get("accent", "orchid")
        )
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._ha_entities: list[dict] = []
        self._ha_entity_map: dict[str, dict] = {}
        self._ha_last_error = ""
        self._avatar_source: Path | None = None
        self._avatar_mtime_ns = -1
        self.system_overview_labels: dict[str, QLabel] = {}
        self.settings_nav_buttons: dict[str, SidebarItemButton] = {}
        self.appearance_buttons: dict[str, QPushButton] = {}
        self.appearance_status: QLabel | None = None
        self.ha_url_input: QLineEdit | None = None
        self.ha_token_input: QLineEdit | None = None
        self.ha_settings_status: QLabel | None = None
        self.ha_summary_label: QLabel | None = None
        self.ha_status_label: QLabel | None = None

        self._brightness_commit_timer = QTimer(self)
        self._brightness_commit_timer.setSingleShot(True)
        self._brightness_commit_timer.timeout.connect(self._commit_brightness)

        self._volume_commit_timer = QTimer(self)
        self._volume_commit_timer.setSingleShot(True)
        self._volume_commit_timer.timeout.connect(self._commit_volume)

        self._build_window()
        self._build_ui()
        self.calendarEventsReady.connect(self._apply_calendar_events)
        self.gameSlidesReady.connect(self._apply_game_slides)
        apply_antialias_font(self)
        self._apply_styles()
        self._apply_media_palette()
        self._start_polls()

    def _build_window(self) -> None:
        self.setWindowTitle("Hanauta Control Center")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.screen_geo = QApplication.primaryScreen().availableGeometry()
        self.compact_size = (884, min(804, self.screen_geo.height() - 72))
        self.settings_size = (
            min(864, self.screen_geo.width() - 72),
            self.compact_size[1],
        )
        self._apply_window_mode("compact")

    def _apply_window_mode(self, mode: str) -> None:
        if mode == "settings":
            width, height = self.settings_size
        else:
            width, height = self.compact_size
        self.resize(width, height)
        self.move(
            self.screen_geo.center().x() - self.width() // 2, self.screen_geo.y() + 28
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("glassPanel")
        self.panel_effect = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.panel_effect)
        self.panel_effect.setOpacity(0.0)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(0)
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.overview_page = self._build_overview_page()
        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.overview_page)
        self.page_stack.addWidget(self.settings_page)
        panel_layout.addWidget(self.page_stack)

        root.addWidget(self.panel)

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addLayout(self._build_header())

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self._build_quick_settings_card())
        left_layout.addWidget(self._build_compact_sliders_card())
        left_layout.addWidget(self._build_media_card())
        left_layout.addWidget(self._build_game_carousel_card())
        left_layout.addWidget(self._build_phone_card())
        left_layout.addWidget(self._build_home_assistant_card())
        left_layout.addStretch(1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self._build_calendar_card())
        right_layout.addWidget(self._build_events_card(), 1)
        right_layout.addWidget(self._build_notifications_card(), 1)

        columns.addWidget(left, 11)
        columns.addWidget(right, 9)
        layout.addLayout(columns, 1)
        self._sync_service_card_visibility()
        return page

    def _section_shell(
        self, title: str, subtitle: str, object_name: str = "overviewSection"
    ) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("sectionSubtitle")
        subtitle_label.setWordWrap(True)
        subtitle_label.setVisible(bool(subtitle.strip()))
        header.addWidget(title_label)
        header.addWidget(subtitle_label)
        layout.addLayout(header)
        return card, layout

    def _build_quick_settings_card(self) -> QFrame:
        card, layout = self._section_shell("Connectivity", "")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        self.quick_buttons = {
            "wifi": QuickSettingButton(
                self.material_font, "Wi-Fi", "wifi", self._toggle_wifi
            ),
            "bluetooth": QuickSettingButton(
                self.material_font, "Bluetooth", "bluetooth", self._toggle_bluetooth
            ),
            "dnd": QuickSettingButton(
                self.material_font, "DND", "do_not_disturb_on", self._toggle_dnd
            ),
            "airplane": QuickSettingButton(
                self.material_font,
                "Airplane",
                "airplanemode_active",
                self._toggle_airplane,
            ),
            "night": QuickSettingButton(
                self.material_font, "Night", "nightlight", self._toggle_night
            ),
            "caffeine": QuickSettingButton(
                self.material_font, "Caffeine", "coffee", self._toggle_caffeine
            ),
        }
        positions = [
            ("wifi", 0, 0),
            ("bluetooth", 0, 1),
            ("dnd", 0, 2),
            ("airplane", 1, 0),
            ("night", 1, 1),
            ("caffeine", 1, 2),
        ]
        for key, row, col in positions:
            button = self.quick_buttons[key]
            button.setMinimumHeight(62)
            grid.addWidget(button, row, col)
        layout.addLayout(grid)
        return card

    def _build_compact_sliders_card(self) -> QFrame:
        card, layout = self._section_shell("Levels", "")
        self.brightness_slider = self._slider_row(
            "brightness_medium", "brightness", compact=True
        )
        self.volume_slider = self._slider_row("volume_up", "volume", compact=True)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.brightness_slider["wrap"], 1)
        row.addWidget(self.volume_slider["wrap"], 1)
        layout.addLayout(row)
        return card

    def _build_game_carousel_card(self) -> QFrame:
        self.game_carousel = GameCarouselCard(self.ui_font, self.material_font)
        self.game_carousel.add_slide(
            "Loading library…",
            ["Fetching recent playtime"],
            Path(STEAM_ICON),
            "Library",
            self.theme_palette.primary,
            Path(),
        )

        def worker() -> None:
            slides: list[dict] = []
            try:
                slides = load_lutris_game_slides(2)
                slides.extend(load_steam_game_slides(2))
            except Exception:
                slides = []
            if not slides:
                slides = [
                    {
                        "title": "Welcome back",
                        "stats": ["No launcher telemetry yet"],
                        "logo": STEAM_ICON,
                        "platform": "Game library",
                        "accent": "primary",
                    }
                ]
            try:
                self.gameSlidesReady.emit(slides[:4])
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        return self.game_carousel

    def _apply_game_slides(self, slides: list) -> None:
        if not hasattr(self, "game_carousel"):
            return
        carousel = self.game_carousel
        if not isinstance(carousel, GameCarouselCard):
            return
        carousel.clear_slides()
        safe_slides = slides if isinstance(slides, list) else []
        for slide in safe_slides[:4]:
            if not isinstance(slide, dict):
                continue
            accent = (
                self.theme_palette.primary
                if slide.get("accent") == "primary"
                else self.theme_palette.secondary
            )
            carousel.add_slide(
                str(slide.get("title", "Game")),
                list(slide.get("stats", [])),
                Path(slide.get("logo", LUTRIS_ICON)),
                str(slide.get("platform", "Library")),
                accent,
                Path(slide.get("cover", Path())),
            )

    def _build_calendar_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("overviewSection")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel("Calendar")
        title_label.setObjectName("sectionTitle")
        self.calendar_settings_btn = self._circle_icon_button("settings")
        self.calendar_settings_btn.setFixedSize(30, 30)
        self.calendar_settings_btn.setFont(QFont(self.material_font, 16))
        self.calendar_settings_btn.setToolTip("Open calendar service settings")
        self.calendar_settings_btn.clicked.connect(
            lambda: self._launch_settings_page("services", "calendar_widget")
        )
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(self.calendar_settings_btn)
        layout.addLayout(header)
        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setObjectName("miniCalendar")
        self.calendar_widget.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.calendar_widget.setGridVisible(False)
        layout.addWidget(self.calendar_widget)
        return card

    def _hidden_scroll(self, name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(6)
        scroll.setWidget(container)
        return scroll, container, inner

    def _build_events_card(self) -> QFrame:
        card, layout = self._section_shell("Upcoming events", "")
        self.events_scroll, self.events_container, self.events_layout = (
            self._hidden_scroll("eventsScroll")
        )
        layout.addWidget(self.events_scroll, 1)
        return card

    def _build_notifications_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("overviewSection")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel("Last notifications")
        title_label.setObjectName("sectionTitle")
        self.clear_notifications_btn = QPushButton(material_icon("delete_sweep"))
        self.clear_notifications_btn.setObjectName("compactIconAction")
        self.clear_notifications_btn.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor)
        )
        self.clear_notifications_btn.setFont(QFont(self.material_font, 16))
        self.clear_notifications_btn.setFixedSize(28, 28)
        self.clear_notifications_btn.setToolTip("Clear all notifications")
        self.clear_notifications_btn.clicked.connect(self._clear_all_notifications)
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(self.clear_notifications_btn)
        layout.addLayout(header)
        (
            self.notifications_scroll,
            self.notifications_container,
            self.notifications_layout,
        ) = self._hidden_scroll("notificationsScroll")
        layout.addWidget(self.notifications_scroll, 1)
        return card

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = QHBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)

        self.avatar = ClickableLabel(self._open_profile_photo_picker)
        self.avatar.setObjectName("avatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(42, 42)
        self.avatar.setFont(QFont(self.material_font, 24))
        self.avatar.setProperty("hasPhoto", False)
        self._refresh_profile_avatar(force=True)

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(2)
        self.user_label = QLabel("User")
        self.user_label.setObjectName("userLabel")
        self.uptime_label = QLabel("up 0 mins")
        self.uptime_label.setObjectName("uptimeLabel")
        self.uptime_label.setFont(QFont(self.mono_font, 9))
        text_wrap.addWidget(self.user_label)
        text_wrap.addWidget(self.uptime_label)

        left.addWidget(self.avatar)
        left.addLayout(text_wrap)

        right = QHBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        self.settings_btn = self._circle_icon_button("settings", rounded_rect=True)
        self.settings_btn.clicked.connect(self._open_settings)
        self.power_btn = self._circle_icon_button(
            "power_settings_new", accent="power", rounded_rect=True
        )
        self.power_btn.clicked.connect(self._open_powermenu)
        right.addWidget(self.settings_btn)
        right.addWidget(self.power_btn)

        layout.addLayout(left)
        layout.addStretch(1)
        layout.addLayout(right)
        return layout

    def _build_quick_settings(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.quick_buttons: dict[str, QuickSettingButton] = {
            "wifi": QuickSettingButton(
                self.material_font, "Wi-Fi", "wifi", self._toggle_wifi
            ),
            "bluetooth": QuickSettingButton(
                self.material_font, "Bluetooth", "bluetooth", self._toggle_bluetooth
            ),
            "dnd": QuickSettingButton(
                self.material_font, "DND", "do_not_disturb_on", self._toggle_dnd
            ),
            "airplane": QuickSettingButton(
                self.material_font,
                "Airplane",
                "airplanemode_active",
                self._toggle_airplane,
            ),
            "night": QuickSettingButton(
                self.material_font, "Night Light", "nightlight", self._toggle_night
            ),
            "caffeine": QuickSettingButton(
                self.material_font, "Caffeine", "coffee", self._toggle_caffeine
            ),
        }
        positions = [
            ("wifi", 0, 0),
            ("bluetooth", 0, 1),
            ("dnd", 1, 0),
            ("airplane", 1, 1),
            ("night", 2, 0),
            ("caffeine", 2, 1),
        ]
        for key, row, col in positions:
            grid.addWidget(self.quick_buttons[key], row, col)
        return grid

    def _build_sliders(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Adjust this value to change the gap between brightness and volume sliders.
        # Lower = tighter (e.g. 4), Higher = more space (e.g. 12).
        slider_row_spacing = 4
        layout.setSpacing(slider_row_spacing)
        self.brightness_slider = self._slider_row("brightness_medium", "brightness")
        self.volume_slider = self._slider_row("volume_up", "volume")
        layout.addWidget(self.brightness_slider["wrap"])
        layout.addWidget(self.volume_slider["wrap"])
        return layout

    def _slider_row(
        self, icon: str, kind: str, compact: bool = False
    ) -> dict[str, QWidget | QSlider]:
        wrap = QFrame()
        wrap.setObjectName("compactSliderWrap" if compact else "sliderWrap")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)

        icon_label = QLabel(material_icon(icon))
        icon_label.setObjectName("sliderIcon")
        icon_label.setFont(QFont(self.material_font, 16 if compact else 18))
        icon_label.setFixedWidth(22)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setObjectName("compactSlider" if compact else "wideSlider")
        slider.valueChanged.connect(
            lambda value, mode=kind: self._queue_slider_commit(mode, value)
        )

        row.addWidget(icon_label)
        row.addWidget(slider, 1)
        return {"wrap": wrap, "slider": slider}

    def _build_media_card(self) -> QFrame:
        self.media_card = QFrame()
        self.media_card.setObjectName("mediaCard")
        self.media_card.setMinimumHeight(132)
        self.media_base = QFrame(self.media_card)
        self.media_base.setObjectName("mediaBase")
        self.media_scrim = QFrame(self.media_card)
        self.media_scrim.setObjectName("mediaScrim")
        self.media_scrim.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.media_content = QWidget(self.media_card)
        self.media_content.setObjectName("mediaContent")

        layout = QVBoxLayout(self.media_content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        self.cover = QLabel()
        self.cover.setObjectName("cover")
        self.cover.setFixedSize(54, 54)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_wrap = QWidget()
        text_wrap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        text = QVBoxLayout(text_wrap)
        text.setContentsMargins(0, 2, 0, 0)
        text.setSpacing(2)
        self.media_title = QLabel("No music")
        self.media_title.setObjectName("mediaTitle")
        self.media_title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.media_title.setMinimumWidth(1)
        self.media_title.setWordWrap(False)
        self.media_artist = QLabel("No artist")
        self.media_artist.setObjectName("mediaArtist")
        self.media_artist.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.media_artist.setMinimumWidth(1)
        self.media_artist.setWordWrap(False)
        text.addWidget(self.media_title)
        text.addWidget(self.media_artist)
        text.addStretch(1)

        top.addWidget(self.cover)
        top.addWidget(text_wrap, 1)
        layout.addLayout(top)

        self.progress_track = QFrame()
        self.progress_track.setObjectName("progressTrack")
        self.progress_fill = QFrame(self.progress_track)
        self.progress_fill.setObjectName("progressFill")
        self.progress_fill.setGeometry(0, 0, 0, 4)
        self.progress_track.setFixedHeight(4)
        layout.addWidget(self.progress_track)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("timeCode")
        self.elapsed.setFont(QFont(self.mono_font, 9))
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        self.prev_btn = self._plain_icon_button("skip_previous")
        self.prev_btn.clicked.connect(lambda: self._trigger_media_action("--previous"))
        self.play_btn = self._circle_icon_button("pause", accent="play")
        self.play_btn.clicked.connect(lambda: self._trigger_media_action("--toggle"))
        self.next_btn = self._plain_icon_button("skip_next")
        self.next_btn.clicked.connect(lambda: self._trigger_media_action("--next"))
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        self.total = QLabel("0:00")
        self.total.setObjectName("timeCode")
        self.total.setFont(QFont(self.mono_font, 9))

        bottom.addWidget(self.elapsed)
        bottom.addStretch(1)
        bottom.addLayout(controls)
        bottom.addStretch(1)
        bottom.addWidget(self.total)
        layout.addLayout(bottom)
        self._sync_media_card_layers()
        return self.media_card

    def _build_phone_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(render_svg_pixmap(KDECONNECT_ICON, 18))
        self.phone_status_dot = QLabel("●")
        self.phone_status_dot.setObjectName("phoneStatusDot")
        self.phone_switch_btn = CompactIconAction(self.material_font, "chevron_right")
        self.phone_switch_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--next")
        )
        self.phone_clipboard_btn = CompactIconAction(
            self.material_font, "content_paste"
        )
        self.phone_clipboard_btn.clicked.connect(
            lambda: run_script_bg("phone_info.sh", "--toggle-clip")
        )
        self.phone_name_value = QLabel("Disconnected")
        self.phone_state_value = QLabel("Offline")
        self.phone_battery_value = QLabel("0%")
        for label in (
            self.phone_name_value,
            self.phone_state_value,
            self.phone_battery_value,
        ):
            label.setObjectName("metricValue")
        self.phone_name_value.setObjectName("inlineMetricPrimary")
        self.phone_state_value.setObjectName("inlineMetric")
        self.phone_battery_value.setObjectName("inlineMetric")
        self.phone_name_value.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        layout.addWidget(icon)
        layout.addWidget(self.phone_name_value, 1)
        layout.addWidget(self.phone_state_value)
        layout.addWidget(self.phone_battery_value)
        layout.addWidget(self.phone_status_dot)
        layout.addWidget(self.phone_clipboard_btn)
        layout.addWidget(self.phone_switch_btn)
        return card

    def _build_home_assistant_card(self) -> QFrame:
        self.ha_card = QFrame()
        self.ha_card.setObjectName("infoCard")
        layout = QHBoxLayout(self.ha_card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        icon = QLabel()
        icon.setObjectName("sectionIcon")
        icon.setFixedWidth(20)
        icon.setPixmap(
            tinted_svg_pixmap(
                HOME_ASSISTANT_ICON, QColor(self.current_accent["accent"]), 18
            )
        )
        self.ha_summary_label = QLabel("")
        self.ha_summary_label.setObjectName("statusHint")
        self.ha_open_settings_btn = CompactIconAction(self.material_font, "settings")
        self.ha_open_settings_btn.clicked.connect(self._open_settings_homeassistant)

        tile_row = QHBoxLayout()
        tile_row.setContentsMargins(0, 0, 0, 0)
        tile_row.setSpacing(4)
        self.ha_action_tiles: list[ActionTile] = []
        for index in range(5):
            tile = ActionTile(
                self.material_font,
                f"Slot {index + 1}",
                "hub",
                lambda checked=False, i=index: self._activate_ha_tile(i),
            )
            tile.setMinimumSize(58, 64)
            tile.setMaximumSize(58, 64)
            self.ha_action_tiles.append(tile)
            tile_row.addWidget(tile)

        self.ha_status_label = QLabel("No entities pinned yet.")
        self.ha_status_label.setObjectName("statusHint")
        self.ha_status_label.hide()
        layout.addWidget(icon)
        layout.addLayout(tile_row, 1)
        layout.addWidget(self.ha_open_settings_btn)
        return self.ha_card

    def _build_vpn_launcher_card(self) -> QFrame:
        self.vpn_launcher_card = ServiceLauncherCard(
            self.material_font,
            "VPN Control",
            "Open the WireGuard popup from the notification center.",
            "lock",
            "Open",
            self._open_vpn_widget,
        )
        return self.vpn_launcher_card

    def _build_christian_launcher_card(self) -> QFrame:
        self.christian_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Christian Widget",
            "Open the devotion widget from the notification center.",
            "auto_awesome",
            "Open",
            self._open_christian_widget,
        )
        return self.christian_launcher_card

    def _build_reminders_launcher_card(self) -> QFrame:
        self.reminders_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Reminders",
            "Open tracked CalDAV reminders and the tea reminder widget.",
            "notifications",
            "Open",
            self._open_reminders_widget,
        )
        return self.reminders_launcher_card

    def _build_pomodoro_launcher_card(self) -> QFrame:
        self.pomodoro_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Pomodoro",
            "Open the focus timer widget with work, short break, and long break modes.",
            "timer",
            "Open",
            self._open_pomodoro_widget,
        )
        return self.pomodoro_launcher_card

    def _build_rss_launcher_card(self) -> QFrame:
        self.rss_launcher_card = ServiceLauncherCard(
            self.material_font,
            "RSS",
            "Open the styled RSS reader for manual feeds or OPML-backed sources.",
            "public",
            "Open",
            self._open_rss_widget,
        )
        return self.rss_launcher_card

    def _build_obs_launcher_card(self) -> QFrame:
        self.obs_launcher_card = ServiceLauncherCard(
            self.material_font,
            "OBS",
            "Open the livestreaming and recording control surface for OBS WebSocket.",
            "videocam",
            "Open",
            self._open_obs_widget,
        )
        return self.obs_launcher_card

    def _build_crypto_launcher_card(self) -> QFrame:
        self.crypto_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Crypto Tracker",
            "Open tracked coins, high-resolution charts, and price alert controls.",
            "show_chart",
            "Open",
            self._open_crypto_widget,
        )
        return self.crypto_launcher_card

    def _build_vps_launcher_card(self) -> QFrame:
        self.vps_launcher_card = ServiceLauncherCard(
            self.material_font,
            "VPS Care",
            "Open SSH-powered VPS health checks, updates, and service restart actions.",
            "storage",
            "Open",
            self._open_vps_widget,
        )
        return self.vps_launcher_card

    def _build_desktop_clock_launcher_card(self) -> QFrame:
        self.desktop_clock_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Desktop Clock",
            "Open the Hanauta analog desktop clock with oversized digital numerals.",
            "watch",
            "Open",
            self._open_desktop_clock_widget,
        )
        return self.desktop_clock_launcher_card

    def _build_game_mode_launcher_card(self) -> QFrame:
        self.game_mode_launcher_card = ServiceLauncherCard(
            self.material_font,
            "Game Mode",
            "Open the Game Mode popup and control the gamemoded user service.",
            "sports_esports",
            "Open",
            self._open_game_mode_popup,
        )
        return self.game_mode_launcher_card

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("settingsContentWrap")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        title = QLabel("Settings moved")
        title.setObjectName("settingsSectionTitle")
        card_layout.addWidget(title)

        subtitle = QLabel(
            "The notification center now opens the standalone Hanauta Settings window so there is only one active settings UI."
        )
        subtitle.setObjectName("settingsSectionSubtitle")
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        open_button = QPushButton("Open Hanauta Settings")
        open_button.setObjectName("softButton")
        open_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_button.clicked.connect(self._open_settings)
        card_layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignLeft)
        card_layout.addStretch(1)

        layout.addWidget(card)
        return page

    def _build_settings_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("System Overview")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel("Quick telemetry for this session and shell environment.")
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.system_overview_grid = QGridLayout()
        self.system_overview_grid.setContentsMargins(0, 8, 0, 0)
        self.system_overview_grid.setHorizontalSpacing(12)
        self.system_overview_grid.setVerticalSpacing(12)
        self.system_overview_labels: dict[str, QLabel] = {}
        for index, key in enumerate(
            ("Host", "Kernel", "Session", "Python", "Uptime", "Screen")
        ):
            label = QLabel("...")
            label.setObjectName("metricValue")
            self.system_overview_labels[key] = label
            self.system_overview_grid.addWidget(
                self._metric_block(key, label), index // 2, index % 2
            )
        layout.addLayout(self.system_overview_grid)
        layout.addStretch(1)
        return page

    def _build_settings_appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("Appearance")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel("Pick an accent preset for the notification center.")
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)
        self.appearance_status = QLabel("")
        self.appearance_status.setObjectName("statusHint")
        layout.addWidget(self.appearance_status)

        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 0)
        row.setSpacing(10)
        self.appearance_buttons: dict[str, QPushButton] = {}
        for key in ("orchid", "mint", "sunset"):
            button = QPushButton(key.title())
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.setObjectName("appearancePreset")
            button.clicked.connect(
                lambda checked=False, current=key: self._set_accent(current)
            )
            self.appearance_buttons[key] = button
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _build_settings_homeassistant_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        header = QLabel("Home Assistant")
        header.setObjectName("settingsSectionTitle")
        sub = QLabel(
            "Connect to your instance, browse entities, and pin up to five controls."
        )
        sub.setObjectName("settingsSectionSubtitle")
        layout.addWidget(header)
        layout.addWidget(sub)

        self.ha_url_input = QLineEdit(
            self.settings_state["home_assistant"].get("url", "")
        )
        self.ha_url_input.setPlaceholderText("https://homeassistant.local:8123")
        self.ha_url_input.setObjectName("settingsInput")
        self.ha_token_input = QLineEdit(
            self.settings_state["home_assistant"].get("token", "")
        )
        self.ha_token_input.setPlaceholderText("Long-lived access token")
        self.ha_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ha_token_input.setObjectName("settingsInput")
        layout.addWidget(self._settings_field("Server URL", self.ha_url_input))
        layout.addWidget(self._settings_field("Long-Lived Token", self.ha_token_input))

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.ha_save_btn = self._soft_button("Save")
        self.ha_save_btn.clicked.connect(self._save_home_assistant_settings)
        self.ha_refresh_btn = self._soft_button("Fetch Entities")
        self.ha_refresh_btn.clicked.connect(self._refresh_home_assistant_entities)
        buttons.addWidget(self.ha_save_btn)
        buttons.addWidget(self.ha_refresh_btn)
        layout.addLayout(buttons)

        self.ha_settings_status = QLabel("Pin up to five entities.")
        self.ha_settings_status.setObjectName("statusHint")
        layout.addWidget(self.ha_settings_status)

        scroll = QScrollArea()
        scroll.setObjectName("entityScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.ha_entity_container = QWidget()
        self.ha_entity_layout = QVBoxLayout(self.ha_entity_container)
        self.ha_entity_layout.setContentsMargins(0, 0, 0, 0)
        self.ha_entity_layout.setSpacing(8)
        self.ha_entity_layout.addStretch(1)
        scroll.setWidget(self.ha_entity_container)
        layout.addWidget(scroll, 1)
        return page

    def _settings_field(self, label_text: str, widget: QWidget) -> QWidget:
        wrap = QWidget()
        row = QVBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        row.addWidget(label)
        row.addWidget(widget)
        return wrap

    def _metric_block(self, title: str, value_label: QLabel) -> QWidget:
        wrap = QFrame()
        wrap.setObjectName("metricCard")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("metricLabel")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return wrap

    def _soft_button(self, title: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("softButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return button

    def _service_enabled(self, key: str) -> bool:
        return bool(
            self.settings_state.get("services", {}).get(key, {}).get("enabled", True)
        )

    def _service_visible_in_notification_center(self, key: str) -> bool:
        service = self.settings_state.get("services", {}).get(key, {})
        return bool(
            service.get("enabled", True)
            and service.get("show_in_notification_center", False)
        )

    def _sync_service_card_visibility(self) -> None:
        if hasattr(self, "ha_card"):
            self.ha_card.setVisible(
                self._service_visible_in_notification_center("home_assistant")
            )
        if hasattr(self, "vpn_launcher_card"):
            self.vpn_launcher_card.setVisible(
                self._service_visible_in_notification_center("vpn_control")
            )
        if hasattr(self, "christian_launcher_card"):
            self.christian_launcher_card.setVisible(
                self._service_visible_in_notification_center("christian_widget")
            )
        if hasattr(self, "reminders_launcher_card"):
            self.reminders_launcher_card.setVisible(
                self._service_visible_in_notification_center("reminders_widget")
            )
        if hasattr(self, "pomodoro_launcher_card"):
            self.pomodoro_launcher_card.setVisible(
                self._service_visible_in_notification_center("pomodoro_widget")
            )
        if hasattr(self, "rss_launcher_card"):
            self.rss_launcher_card.setVisible(
                self._service_visible_in_notification_center("rss_widget")
            )
        if hasattr(self, "obs_launcher_card"):
            self.obs_launcher_card.setVisible(
                self._service_visible_in_notification_center("obs_widget")
            )
        if hasattr(self, "crypto_launcher_card"):
            self.crypto_launcher_card.setVisible(
                self._service_visible_in_notification_center("crypto_widget")
            )
        if hasattr(self, "vps_launcher_card"):
            self.vps_launcher_card.setVisible(
                self._service_visible_in_notification_center("vps_widget")
            )
        if hasattr(self, "desktop_clock_launcher_card"):
            self.desktop_clock_launcher_card.setVisible(
                self._service_visible_in_notification_center("desktop_clock_widget")
            )
        if hasattr(self, "game_mode_launcher_card"):
            self.game_mode_launcher_card.setVisible(
                self._service_visible_in_notification_center("game_mode")
            )

    def _open_vpn_widget(self) -> None:
        if not self._service_enabled("vpn_control") or not VPN_CONTROL_SCRIPT.exists():
            return
        run_bg_singleton(VPN_CONTROL_SCRIPT)

    def _open_christian_widget(self) -> None:
        if (
            not self._service_enabled("christian_widget")
            or not CHRISTIAN_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(CHRISTIAN_WIDGET_SCRIPT)

    def _open_reminders_widget(self) -> None:
        if (
            not self._service_enabled("reminders_widget")
            or not REMINDERS_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(REMINDERS_WIDGET_SCRIPT)

    def _open_pomodoro_widget(self) -> None:
        if (
            not self._service_enabled("pomodoro_widget")
            or not POMODORO_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(POMODORO_WIDGET_SCRIPT)

    def _open_rss_widget(self) -> None:
        rss_widget_script = resolve_rss_widget_script(self.settings_state)
        if not self._service_enabled("rss_widget") or not rss_widget_script.exists():
            return
        run_bg_singleton(rss_widget_script)

    def _open_obs_widget(self) -> None:
        if not self._service_enabled("obs_widget") or not OBS_WIDGET_SCRIPT.exists():
            return
        run_bg_singleton(OBS_WIDGET_SCRIPT)

    def _open_crypto_widget(self) -> None:
        if (
            not self._service_enabled("crypto_widget")
            or not CRYPTO_WIDGET_SCRIPT.exists()
        ):
            return
        run_bg_singleton(CRYPTO_WIDGET_SCRIPT)

    def _open_vps_widget(self) -> None:
        if not self._service_enabled("vps_widget") or not VPS_WIDGET_SCRIPT.exists():
            return
        run_bg_singleton(VPS_WIDGET_SCRIPT)

    def _open_desktop_clock_widget(self) -> None:
        if not self._service_enabled("desktop_clock_widget"):
            return
        command = desktop_clock_command()
        if not command:
            return
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _open_game_mode_popup(self) -> None:
        if (
            not self._service_enabled("game_mode")
            or not GAME_MODE_POPUP_SCRIPT.exists()
        ):
            return
        run_bg_singleton(GAME_MODE_POPUP_SCRIPT)

    def _circle_icon_button(
        self, icon: str, accent: str = "default", rounded_rect: bool = False
    ) -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setProperty("accent", accent)
        button.setProperty("roundedRect", rounded_rect)
        button.setObjectName("circleIconButton")
        button.setFixedSize(40, 40)
        return button

    def _plain_icon_button(self, icon: str) -> QPushButton:
        button = QPushButton(material_icon(icon))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 20))
        button.setObjectName("plainIconButton")
        button.setFixedSize(28, 28)
        return button

    def _apply_styles(self) -> None:
        theme = self.theme_palette
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}", "Rubik", "Noto Sans", sans-serif;
            }}
            #glassPanel {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 28px;
            }}
            #pageStack {{
                background: transparent;
            }}
            #overviewSection, #infoCard, #settingsContentWrap, #sidebar, #gameCarouselCard {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 22px;
            }}
            #avatar {{
                background: qlineargradient(x1:0, y1:1, x2:1, y2:0, stop:0 {theme.primary}, stop:1 {theme.tertiary});
                color: {theme.active_text};
                font-family: "{self.material_font}";
                border-radius: 23px;
                border: none;
                padding: 0px;
            }}
            #avatar[hasPhoto="true"] {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            #userLabel {{
                font-size: 17px;
                font-weight: 600;
                color: {theme.text};
            }}
            #uptimeLabel {{
                color: {theme.text_muted};
            }}
            #circleIconButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: none;
                border-radius: 999px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #circleIconButton[roundedRect="true"] {{
                border-radius: 14px;
            }}
            #circleIconButton:hover {{
                background: {theme.hover_bg};
            }}
            #circleIconButton[accent="power"] {{
                background: {theme.error};
                color: {theme.on_error};
            }}
            #circleIconButton[accent="power"]:hover {{
                background: {theme.error};
            }}
            #sliderWrap, #compactSliderWrap {{
                background: transparent;
            }}
            #sectionIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #sectionTitle, #settingsTitle, #settingsSectionTitle {{
                font-size: 15px;
                font-weight: 600;
                color: {theme.text};
            }}
            #sectionSubtitle, #settingsSectionSubtitle, #statusHint {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            #metricCard {{
                background: {theme.app_running_bg};
                border: 1px solid {theme.app_running_border};
                border-radius: 14px;
            }}
            #metricLabel {{
                color: {theme.inactive};
                font-size: 10px;
                text-transform: uppercase;
            }}
            #metricValue {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 600;
            }}
            #inlineMetricPrimary {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 600;
            }}
            #inlineMetric {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 500;
            }}
            #softButton {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                padding: 8px 12px;
                font-weight: 500;
            }}
            #softButton:hover {{
                background: {theme.hover_bg};
            }}
            #actionTile {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
            }}
            #actionTile:hover {{
                background: {theme.hover_bg};
            }}
            #actionTileIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #actionTileTitle {{
                color: {theme.text};
                font-size: 10px;
                font-weight: 600;
            }}
            #actionTileSubtitle {{
                color: {theme.text_muted};
                font-size: 9px;
            }}
            #compactIconAction {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: none;
                border-radius: 999px;
                color: {theme.icon};
                font-family: "{self.material_font}";
            }}
            #compactIconAction:hover {{
                background: {theme.hover_bg};
            }}
            #compactIconAction[active="true"] {{
                background: {theme.accent_soft};
                color: {theme.primary};
            }}
            #compactIconAction:disabled {{
                color: {theme.inactive};
                background: {rgba(theme.surface_container_high, 0.44)};
            }}
            #settingsInput {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 999px;
                color: {theme.text};
                padding: 12px 14px;
            }}
            #fieldLabel {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            #entityScroll {{
                background: transparent;
            }}
            #phoneStatusDot {{
                color: {theme.primary};
                font-size: 16px;
            }}
            #appearancePreset {{
                background: {rgba(theme.surface_container_high, 0.88)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 16px;
                color: {theme.text};
                padding: 16px 18px;
                font-weight: 600;
            }}
            #appearancePreset:hover {{
                background: {theme.hover_bg};
            }}
            #sliderIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #compactSliderWrap {{
                background: {rgba(theme.surface_container_high, 0.34)};
                border: none;
                border-radius: 14px;
            }}
            #wideSlider::groove:horizontal, #compactSlider::groove:horizontal {{
                background: {rgba(theme.on_surface_variant, 0.12)};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider, #compactSlider {{
                background: transparent;
                border: none;
            }}
            #wideSlider::groove:horizontal {{
                height: 42px;
            }}
            #compactSlider::groove:horizontal {{
                height: 16px;
            }}
            #wideSlider::sub-page:horizontal, #compactSlider::sub-page:horizontal {{
                background: {theme.primary};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider::add-page:horizontal, #compactSlider::add-page:horizontal {{
                background: {rgba(theme.on_surface_variant, 0.12)};
                border-radius: 999px;
                margin: 0px;
            }}
            #wideSlider::handle:horizontal, #compactSlider::handle:horizontal {{
                background: transparent;
                width: 0px;
                margin: 0;
            }}
            #gameStack {{
                background: transparent;
                border: none;
            }}
            #gameCarouselCard {{
                background: qlineargradient(x1:0, y1:1, x2:1, y2:0,
                    stop:0 {rgba(theme.surface_container_high, 0.92)},
                    stop:1 {rgba(theme.primary_container, 0.72)});
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 20px;
            }}
            #gameSlideInner {{
                background: transparent;
                border: none;
                min-height: 104px;
            }}
            #gameKicker {{
                color: {theme.text};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            #gameCarouselTitle, #gameSlideTitle {{
                color: {theme.text};
                font-size: 14px;
                font-weight: 600;
            }}
            #gameSlidePlatform, #gameCaption, #feedCardMeta {{
                color: {theme.text_muted};
                font-size: 9px;
                font-weight: 500;
            }}
            #gameStatChip {{
                background: {theme.primary};
                color: {theme.active_text};
                border-radius: 10px;
                padding: 3px 8px;
                font-size: 9px;
                font-weight: 600;
            }}
            #gameStatLabel {{
                color: {theme.primary};
                background: {rgba(theme.primary, 0.14)};
                border: 1px solid {rgba(theme.primary, 0.18)};
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 9px;
                font-weight: 500;
            }}
            #gameSlideHint {{
                color: {theme.inactive};
                font-size: 9px;
            }}
            #carouselDot {{
                color: {rgba(theme.on_surface_variant, 0.30)};
                font-size: 14px;
            }}
            #carouselDot[active="true"] {{
                color: {theme.primary};
            }}
            #miniCalendar {{
                background: transparent;
                border: none;
                border-radius: 16px;
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
                alternate-background-color: transparent;
                color: {theme.text};
            }}
            #miniCalendar QWidget {{
                background: transparent;
                outline: none;
            }}
            #miniCalendar QAbstractItemView:focus,
            #miniCalendar QTableView:focus,
            #miniCalendar QSpinBox:focus,
            #miniCalendar QToolButton:focus {{
                outline: none;
            }}
            #miniCalendar QToolButton {{
                color: {theme.text};
                font-weight: 600;
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 4px 6px;
            }}
            #miniCalendar QToolButton:hover {{
                background: {rgba(theme.surface_container_high, 0.56)};
            }}
            #miniCalendar QToolButton#qt_calendar_monthbutton,
            #miniCalendar QToolButton#qt_calendar_yearbutton {{
                font-size: 12px;
            }}
            #miniCalendar QToolButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            #miniCalendar QMenu {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                color: {theme.text};
            }}
            #miniCalendar QAbstractItemView:enabled {{
                color: {theme.text};
                background: {rgba(theme.surface_container_high, 0.18)};
                border: 1px solid {rgba(theme.outline, 0.12)};
                border-radius: 12px;
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
                alternate-background-color: transparent;
                gridline-color: transparent;
                outline: 0;
            }}
            #miniCalendar QWidget#qt_calendar_navigationbar {{
                background: transparent;
            }}
            #miniCalendar QSpinBox {{
                background: transparent;
                color: {theme.text};
                border: none;
                border-radius: 10px;
                padding: 2px 4px;
                selection-background-color: {theme.primary};
            }}
            #miniCalendar QAbstractItemView {{
                background: {theme.chip_bg};
                color: {theme.text};
                border: 1px solid {theme.chip_border};
                selection-background-color: {theme.primary};
                selection-color: {theme.active_text};
            }}
            #miniCalendar QTableView {{
                background: transparent;
                border: none;
            }}
            #feedCard {{
                background: {rgba(theme.surface_container_high, 0.76)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 14px;
            }}
            #feedCardIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
            }}
            #feedCardTitle {{
                color: {theme.text};
                font-size: 11px;
                font-weight: 600;
            }}
            #feedCardBody {{
                color: {theme.text_muted};
                font-size: 10px;
            }}
            #notificationCloseButton {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: none;
                border-radius: 10px;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            #notificationCloseButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            #eventsScroll, #notificationsScroll {{
                background: transparent;
                border: none;
            }}
            #eventsScroll QScrollBar:vertical, #notificationsScroll QScrollBar:vertical {{
                width: 0px;
                background: transparent;
            }}
            #eventsScroll QScrollBar::handle:vertical, #notificationsScroll QScrollBar::handle:vertical {{
                background: transparent;
            }}
            #mediaCard {{
                background: {rgba(theme.surface_container_high, 0.82)};
                border: 1px solid {rgba(theme.outline, 0.16)};
                border-radius: 18px;
            }}
            #cover {{
                background: {theme.surface_container_high};
                border: 1px solid {theme.chip_border};
                border-radius: 14px;
            }}
            #mediaTitle {{
                font-size: 13px;
                font-weight: 500;
                color: {theme.text};
            }}
            #mediaArtist {{
                font-size: 11px;
                color: {theme.primary};
            }}
            #progressTrack {{
                background: {theme.app_running_border};
                border-radius: 2px;
            }}
            #progressFill {{
                background: {theme.primary};
                border-radius: 2px;
            }}
            #plainIconButton {{
                background: transparent;
                border: none;
                color: {theme.text_muted};
                font-family: "{self.material_font}";
            }}
            #plainIconButton:hover {{
                color: {theme.primary};
            }}
            #quickTileIcon {{
                font-family: "{self.material_font}";
            }}
            #timeCode {{
                color: {theme.inactive};
                font-size: 10px;
            }}
            """
        )
        self._apply_calendar_formats()
        for quick_button in getattr(self, "quick_buttons", {}).values():
            quick_button.apply_theme(
                theme, self.current_accent["accent"], self.current_accent["on_accent"]
            )
        for button_key, button in getattr(self, "settings_nav_buttons", {}).items():
            current_index = (
                self.settings_stack.currentIndex()
                if hasattr(self, "settings_stack")
                else 0
            )
            key_to_index = {"overview": 0, "appearance": 1, "homeassistant": 2}
            button.apply_state(
                key_to_index.get(button_key, -1) == current_index,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                theme,
            )

    def _apply_media_palette(
        self,
        start: str | None = None,
        end: str | None = None,
        border: str | None = None,
        accent: str | None = None,
    ) -> None:
        if not hasattr(self, "media_base"):
            return
        theme = self.theme_palette
        start = start or theme.media_active_start
        end = end or theme.media_active_end
        border = border or theme.media_active_border
        accent = accent or self.current_accent["accent"]
        self.media_base.setStyleSheet(
            f"""
            background: qradialgradient(
                cx: 0.36, cy: 0.26, radius: 0.95, fx: 0.36, fy: 0.26,
                stop: 0 {start},
                stop: 0.38 {end},
                stop: 1 {theme.panel_bg}
            );
            border-radius: 20px;
            """
        )
        self.media_card.setStyleSheet(
            f"""
            QFrame#mediaCard {{
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )
        self.media_scrim.setStyleSheet(
            """
            background: qradialgradient(
                cx: 0.5, cy: 0.36, radius: 1.05, fx: 0.5, fy: 0.34,
                stop: 0 rgba(0, 0, 0, 0.25),
                stop: 0.48 rgba(0, 0, 0, 0.58),
                stop: 1 rgba(0, 0, 0, 1.0)
            );
            border-radius: 20px;
            """
        )
        self.progress_fill.setStyleSheet(f"background: {accent}; border-radius: 2px;")
        self.media_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {theme.text};"
        )
        self.media_artist.setStyleSheet(f"font-size: 12px; color: {accent};")
        self.play_btn.setStyleSheet(
            f"""
            background: {accent};
            border: none;
            border-radius: 20px;
            color: {theme.active_text};
            font-family: "{self.material_font}";
            """
        )

    def _sync_media_card_layers(self) -> None:
        if not hasattr(self, "media_card"):
            return
        media_rect = self.media_card.rect()
        self.media_base.setGeometry(media_rect)
        self.media_scrim.setGeometry(media_rect)
        self.media_content.setGeometry(media_rect)

    def _start_polls(self) -> None:
        # Defer expensive subprocess polling until after the first paint so the
        # window appears instantly.
        QTimer.singleShot(0, self._poll_all)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_all)
        self.timer.start(3500)

        self.ha_timer = QTimer(self)
        self.ha_timer.timeout.connect(self._refresh_home_assistant_entities)
        self.ha_timer.start(15000)

        if hasattr(self, "media_card"):
            self.media_progress_timer = QTimer(self)
            self.media_progress_timer.timeout.connect(self._poll_media_progress)
            self.media_progress_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.calendar_timer = QTimer(self)
        self.calendar_timer.timeout.connect(self._request_calendar_refresh)
        self.calendar_timer.start(30000)
        QTimer.singleShot(150, self._request_calendar_refresh)

        QTimer.singleShot(80, self._animate_in)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme_palette = load_theme_palette()
        if self.theme_palette.use_matugen:
            self.current_accent = {
                "accent": self.theme_palette.primary,
                "on_accent": self.theme_palette.active_text,
                "soft": self.theme_palette.accent_soft,
            }
        self._apply_styles()
        self._apply_media_palette()
        self._render_home_assistant_tiles()

    def _animate_in(self) -> None:
        self._panel_animation = QPropertyAnimation(self.panel_effect, b"opacity", self)
        self._panel_animation.setDuration(260)
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.start()

    def _poll_all(self) -> None:
        self._poll_header()
        self._poll_quick_settings()
        self._poll_sliders()
        self._poll_media_metadata()
        self._poll_media_progress()
        self._poll_phone()
        self._render_calendar_events()
        self._poll_notification_history()
        self._refresh_system_overview()
        self._render_home_assistant_tiles()

    def _apply_calendar_events(self, events: list) -> None:
        self._calendar_fetch_in_progress = False
        self._calendar_events = (
            [item for item in events if isinstance(item, dict)]
            if isinstance(events, list)
            else []
        )
        self._render_calendar_events(force=True)

    def _poll_header(self) -> None:
        self.user_label.setText(os.environ.get("USER", "User"))
        uptime = run_cmd(["uptime", "-p"]).removeprefix(
            "up "
        ).strip() or datetime.now().strftime("%H:%M")
        self.uptime_label.setText(f"up {uptime}")
        self._refresh_profile_avatar()

    def _poll_phone(self) -> None:
        raw = run_script("phone_info.sh")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        name = str(payload.get("name", "Disconnected"))
        battery = str(payload.get("battery", "0"))
        status = str(payload.get("status", "Offline"))
        clipboard = str(payload.get("clipboard", "off"))
        has_device = bool(payload.get("id")) and name != "Disconnected"
        if has_device:
            self.phone_name_value.setText(name)
            self.phone_state_value.setText(status)
            self.phone_battery_value.setText(f"{battery}%")
        else:
            self.phone_name_value.setText("No devices connected")
            self.phone_state_value.setText("")
            self.phone_battery_value.setText("")
        self.phone_status_dot.setStyleSheet(
            f"color: {self.theme_palette.primary if has_device and status.lower() != 'offline' else self.theme_palette.workspace_empty};"
        )
        self.phone_clipboard_btn.set_active(has_device and clipboard == "on")
        self.phone_clipboard_btn.setEnabled(has_device)
        self.phone_switch_btn.setEnabled(has_device)

    def _refresh_system_overview(self) -> None:
        if not self.system_overview_labels:
            return
        metrics = {
            "Host": run_cmd(["hostname"]) or "Unknown",
            "Kernel": run_cmd(["uname", "-r"]) or "Unknown",
            "Session": os.environ.get("XDG_SESSION_DESKTOP", "i3"),
            "Python": sys.version.split()[0],
            "Uptime": self.uptime_label.text(),
            "Screen": f"{self.width()}x{self.height()}",
        }
        for key, value in metrics.items():
            label = self.system_overview_labels.get(key)
            if label is not None:
                label.setText(value)

    def _clear_layout_widgets(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    child = child_layout.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()

    def _history_item_id(self, payload: dict) -> int:
        raw = payload.get("id", 0)
        if isinstance(raw, dict):
            raw = raw.get("id", raw.get("value", raw.get("data", 0)))
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    def _history_item_matches(self, left: dict, right: dict) -> bool:
        left_id = self._history_item_id(left)
        right_id = self._history_item_id(right)
        if left_id and right_id:
            return left_id == right_id
        return (
            str(left.get("app_name", "")) == str(right.get("app_name", ""))
            and str(left.get("summary", "")) == str(right.get("summary", ""))
            and str(left.get("body", "")) == str(right.get("body", ""))
            and str(left.get("timestamp", "")) == str(right.get("timestamp", ""))
        )

    def _write_notification_history(self, history: list[dict]) -> None:
        _atomic_write_json(NOTIFICATION_HISTORY_FILE, history)

    def _dismiss_notification(self, target: dict) -> None:
        updated: list[dict] = []
        removed = False
        for item in self._notification_history:
            if not removed and self._history_item_matches(item, target):
                removed = True
                continue
            updated.append(item)
        self._write_notification_history(updated)
        self._poll_notification_history()

    def _clear_all_notifications(self) -> None:
        self._write_notification_history([])
        self._poll_notification_history()

    def _list_item_card(
        self,
        title: str,
        subtitle: str,
        meta: str,
        kind: str,
        icon_pixmap: QPixmap | None = None,
        action_button: QPushButton | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("feedCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(10)

        icon = QLabel(
            material_icon(kind) if icon_pixmap is None or icon_pixmap.isNull() else ""
        )
        icon.setObjectName("feedCardIcon")
        icon.setFont(QFont(self.material_font, 16))
        icon.setFixedWidth(20)
        if icon_pixmap is not None and not icon_pixmap.isNull():
            icon.setPixmap(icon_pixmap)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("feedCardTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("feedCardBody")
        subtitle_label.setWordWrap(True)
        meta_label = QLabel(meta)
        meta_label.setObjectName("feedCardMeta")
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        text.addWidget(meta_label)
        row.addLayout(text, 1)
        if action_button is not None:
            row.addWidget(action_button, 0, Qt.AlignmentFlag.AlignTop)
        return card

    def _notification_icon_pixmap(
        self,
        app_name: str,
        desktop_entry: str = "",
        icon_name: str = "",
        summary: str = "",
        body: str = "",
    ) -> QPixmap:
        normalized = app_name.strip().lower()
        summary_normalized = summary.strip().lower()
        body_normalized = body.strip().lower()
        if icon_name:
            direct_icon_path = Path(icon_name.replace("file://", "")).expanduser()
            if direct_icon_path.exists():
                direct = render_svg_pixmap(direct_icon_path, 18)
                if not direct.isNull():
                    return direct
        is_caffeine = (
            "caffeine" in normalized
            or "caffeine" in summary_normalized
            or "caffeine" in body_normalized
        )
        if is_caffeine:
            caffeine_path = Path(CAFFEINE_NOTIFICATION_ICON).expanduser()
            if caffeine_path.exists():
                return tinted_svg_pixmap(
                    caffeine_path, QColor(self.theme_palette.primary), 18
                )
            fallback = render_theme_icon_pixmap(["coffee"], 18)
            if not fallback.isNull():
                return fallback
        is_night_light = (
            "night light" in normalized
            or "nightlight" in normalized
            or "night light" in summary_normalized
            or "nightlight" in summary_normalized
            or "night light" in body_normalized
            or "nightlight" in body_normalized
            or icon_name.strip().lower() in {"nightlight", "weather-clear-night"}
        )
        if is_night_light:
            night_path = Path(NIGHT_LIGHT_NOTIFICATION_ICON).expanduser()
            if night_path.exists():
                return tinted_svg_pixmap(
                    night_path, QColor(self.theme_palette.primary), 18
                )
            fallback = render_theme_icon_pixmap(["nightlight", "weather-clear-night"], 18)
            if not fallback.isNull():
                return fallback
        is_weather = (
            "weather" in normalized
            or "weather" in summary_normalized
            or "weather" in body_normalized
            or "sunrise" in summary_normalized
            or "sunset" in summary_normalized
            or "sunrise" in body_normalized
            or "sunset" in body_normalized
        )
        if is_weather and WEATHER_HISTORY_ICON.exists():
            return tinted_svg_pixmap(
                WEATHER_HISTORY_ICON, QColor(self.theme_palette.primary), 18
            )
        known_assets = {
            "kde connect": KDECONNECT_ICON,
            "kdeconnect": KDECONNECT_ICON,
            "home assistant": HOME_ASSISTANT_ICON,
            "steam": STEAM_ICON,
            "lutris": LUTRIS_ICON,
        }
        asset = known_assets.get(normalized)
        if asset is not None:
            return tinted_svg_pixmap(asset, QColor(self.theme_palette.primary), 18)

        theme_name_candidates = {
            "kde connect": ["kdeconnect", "org.kde.kdeconnect", "kde-connect"],
            "kdeconnect": ["kdeconnect", "org.kde.kdeconnect", "kde-connect"],
            "discord": ["discord", "Discord"],
            "spotify": ["spotify", "Spotify"],
            "steam": ["steam", "Steam"],
            "lutris": ["lutris", "Lutris"],
            "telegram": ["telegram", "Telegram", "org.telegram.desktop"],
            "firefox": ["firefox", "Firefox"],
            "chromium": ["chromium", "Chromium"],
            "google chrome": ["google-chrome", "Google-chrome", "chrome"],
            "ferdium": ["ferdium", "Ferdium"],
        }
        candidates = []
        if icon_name:
            candidates.append(icon_name)
        if desktop_entry:
            candidates.extend(
                [
                    desktop_entry,
                    desktop_entry.removesuffix(".desktop"),
                    desktop_entry.replace(".desktop", ""),
                ]
            )
        candidates.extend(theme_name_candidates.get(normalized, []))
        if not candidates:
            slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
            dotted = re.sub(r"[^a-z0-9]+", ".", normalized).strip(".")
            compact = re.sub(r"[^a-z0-9]+", "", normalized)
            candidates = [slug, dotted, compact, app_name]
        return render_theme_icon_pixmap(candidates, 18)

    def _apply_calendar_formats(self) -> None:
        if not hasattr(self, "calendar_widget"):
            return
        theme = self.theme_palette

        header_fmt = QTextCharFormat()
        header_fmt.setForeground(QColor(theme.primary))
        self.calendar_widget.setHeaderTextFormat(header_fmt)

        weekday_fmt = QTextCharFormat()
        weekday_fmt.setForeground(QColor(theme.text))
        weekend_fmt = QTextCharFormat()
        weekend_fmt.setForeground(QColor(theme.primary))

        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Monday, weekday_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Tuesday, weekday_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Wednesday, weekday_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Thursday, weekday_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Friday, weekday_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_fmt)
        self.calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_fmt)

        today_fmt = QTextCharFormat()
        today_fmt.setForeground(QColor(theme.text))
        today_fmt.setBackground(QColor(self._hex_to_rgba(theme.primary, 0.16)))
        self.calendar_widget.setDateTextFormat(QDate.currentDate(), today_fmt)

    def _request_calendar_refresh(self) -> None:
        if self._calendar_fetch_in_progress:
            return
        self._calendar_fetch_in_progress = True
        self._calendar_last_fetch = monotonic()

        def worker() -> None:
            events = load_calendar_events(2)
            try:
                self.calendarEventsReady.emit(events)
            except Exception:
                pass

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _render_calendar_events(self, *, force: bool = False) -> None:
        try:
            signature = json.dumps(self._calendar_events, sort_keys=True)
        except Exception:
            signature = str(self._calendar_events)
        if not force and signature == self._calendar_render_signature:
            return
        self._calendar_render_signature = signature

        if self._calendar_events:
            title = str(self._calendar_events[0].get("title", "")).strip()
            if title == "Calendar sync error":
                err = str(self._calendar_events[0].get("start", "")).strip()
                if err and err != self._calendar_last_error:
                    self._calendar_last_error = err
                    try:
                        print(f"[hanauta] calendar error: {err}", file=sys.stderr)
                    except Exception:
                        pass
            elif self._calendar_last_error:
                self._calendar_last_error = ""
                try:
                    print("[hanauta] calendar recovered", file=sys.stderr)
                except Exception:
                    pass
        self._clear_layout_widgets(self.events_layout)
        calendar_icon_pixmap = QPixmap()
        calendar_icon_path = Path(CALENDAR_NOTIFICATION_ICON).expanduser()
        if calendar_icon_path.exists():
            calendar_icon_pixmap = tinted_svg_pixmap(
                calendar_icon_path, QColor(self.theme_palette.primary), 18
            )
        if not self._calendar_events:
            self.events_layout.addWidget(
                self._list_item_card(
                    "No upcoming events",
                    "Connect a CalDAV calendar to populate this area.",
                    "Nothing scheduled in the next 14 days",
                    "calendar_today",
                    calendar_icon_pixmap,
                )
            )
            self.events_layout.addStretch(1)
            return
        for event in self._calendar_events:
            title = str(event.get("title", "Untitled event"))
            start_text = str(event.get("start", ""))
            try:
                moment = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
                meta = moment.strftime("%a • %d %b • %H:%M")
            except Exception:
                meta = start_text or "Upcoming"
            location = str(event.get("location", "")).strip()
            subtitle = location or "Calendar event"
            self.events_layout.addWidget(
                self._list_item_card(
                    title,
                    subtitle,
                    meta,
                    "calendar_today",
                    calendar_icon_pixmap,
                )
            )
        self.events_layout.addStretch(1)

    def _poll_notification_history(self) -> None:
        self._notification_history = load_notification_history(3)
        self._clear_layout_widgets(self.notifications_layout)
        if hasattr(self, "clear_notifications_btn"):
            self.clear_notifications_btn.setEnabled(bool(self._notification_history))
        if not self._notification_history:
            self.notifications_layout.addWidget(
                self._list_item_card(
                    "No recent notifications",
                    "Your notification history will appear here once the daemon records alerts.",
                    "History is currently empty",
                    "notifications",
                )
            )
            self.notifications_layout.addStretch(1)
            return
        for item in self._notification_history:
            title = str(item.get("summary", "Notification")).strip() or "Notification"
            body = str(item.get("body", "")).replace("\n", " ").strip() or str(
                item.get("app_name", "No details")
            )
            app_name = str(item.get("app_name", "System")).strip() or "System"
            desktop_entry = str(item.get("desktop_entry", "")).strip()
            icon_name = str(item.get("icon", "")).strip()
            dismiss_btn = QPushButton(material_icon("close"))
            dismiss_btn.setObjectName("notificationCloseButton")
            dismiss_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dismiss_btn.setFont(QFont(self.material_font, 14))
            dismiss_btn.setFixedSize(20, 20)
            dismiss_btn.setToolTip("Dismiss notification")
            dismiss_btn.clicked.connect(
                lambda checked=False, current=dict(item): self._dismiss_notification(
                    current
                )
            )
            self.notifications_layout.addWidget(
                self._list_item_card(
                    title,
                    body,
                    app_name,
                    "notifications",
                    self._notification_icon_pixmap(
                        app_name,
                        desktop_entry,
                        icon_name,
                        title,
                        body,
                    ),
                    dismiss_btn,
                )
            )
        self.notifications_layout.addStretch(1)

    def _poll_quick_settings(self) -> None:
        wifi_on = run_script("network.sh", "status") == "Connected"
        wifi_ssid = run_script("network.sh", "ssid") or "Disconnected"
        self.quick_buttons["wifi"].set_state(wifi_on, "wifi", wifi_ssid)

        bt_on = run_script("bluetooth", "state") == "on"
        self.quick_buttons["bluetooth"].set_state(
            bt_on, "bluetooth", "Connected" if bt_on else "Off"
        )

        dnd_on = parse_bool_text(run_cmd(notification_control_command("is-paused")))
        self.quick_buttons["dnd"].set_state(
            dnd_on, "do_not_disturb_on", "On" if dnd_on else "Off"
        )

        airplane_on = run_script("network.sh", "radio-status") == "off"
        self.quick_buttons["airplane"].set_state(
            airplane_on, "airplanemode_active", "On" if airplane_on else "Off"
        )

        night_on = run_script("redshift", "state") == "on"
        self.quick_buttons["night"].set_state(
            night_on, "nightlight", "On" if night_on else "Off"
        )

        caffeine_on = run_script("caffeine.sh", "status") == "on"
        self.quick_buttons["caffeine"].set_state(
            caffeine_on, "coffee", "On" if caffeine_on else "Off"
        )

    def _poll_sliders(self) -> None:
        self._syncing_sliders = True
        try:
            self.brightness_slider["slider"].setValue(
                int(run_script("brightness.sh", "br") or "67")
            )
        except Exception:
            self.brightness_slider["slider"].setValue(67)
        try:
            self.volume_slider["slider"].setValue(
                int(run_script("volume.sh", "vol") or "82")
            )
        except Exception:
            self.volume_slider["slider"].setValue(82)
        self._syncing_sliders = False

    def _poll_media_metadata(self) -> None:
        if not hasattr(self, "media_title"):
            return
        title = run_script("mpris.sh", "title") or "No music"
        artist = run_script("mpris.sh", "artist") or "No artist"
        status = run_script("mpris.sh", "status") or "Stopped"
        player = run_script("mpris.sh", "player")
        art = run_script("mpris.sh", "coverloc")
        media_url = ""
        if player:
            media_url = run_cmd(
                [
                    "playerctl",
                    f"--player={player}",
                    "metadata",
                    "--format",
                    "{{xesam:url}}",
                ]
            )

        self._media_player = player
        self._media_status = status
        self._media_last_sync = monotonic()
        self._media_url = media_url
        self.media_title.setText(title)
        self.media_artist.setText(artist)
        self.media_title.setVisible(True)
        self.media_artist.setVisible(True)
        self.media_title.updateGeometry()
        self.media_artist.updateGeometry()
        self.media_title.repaint()
        self.media_artist.repaint()
        self.play_btn.setText(
            material_icon("pause" if status == "Playing" else "play_arrow")
        )

        track_key = f"{title}|{artist}"
        if track_key != self._media_track_key:
            self._media_track_key = track_key
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._media_estimated_progress = False
            self._render_media_progress()
            if self._is_browser_player(player) and media_url:
                self._request_media_url_duration(media_url)
            cover_path = Path(art) if art else FALLBACK_COVER
            if not cover_path.exists():
                cover_path = FALLBACK_COVER
            self._set_cover_art(cover_path)
            self._update_media_palette_from_cover(cover_path)

    def _is_browser_player(self, player: str) -> bool:
        lowered = player.lower()
        return any(
            name in lowered
            for name in (
                "firefox",
                "librewolf",
                "chromium",
                "brave",
                "chrome",
                "vivaldi",
            )
        )

    def _duration_ms_from_media_url(self, url: str) -> int | None:
        url = url.strip()
        if not url:
            return None
        cached = self._media_duration_cache.get(url)
        if cached is not None:
            return cached
        duration_raw = run_cmd(
            [
                "yt-dlp",
                "--no-playlist",
                "--skip-download",
                "--print",
                "duration",
                "--no-warnings",
                url,
            ],
            timeout=4.0,
        )
        try:
            duration_ms = max(0, int(float(duration_raw.strip()) * 1000))
        except Exception:
            return None
        self._media_duration_cache[url] = duration_ms
        return duration_ms

    def _request_media_url_duration(self, url: str) -> None:
        url = url.strip()
        if (
            not url
            or url in self._media_duration_cache
            or url in self._media_duration_pending
        ):
            return
        self._media_duration_pending.add(url)

        def worker() -> None:
            try:
                duration_ms = self._duration_ms_from_media_url(url)
                if duration_ms is not None:
                    self._media_duration_cache[url] = duration_ms
            finally:
                self._media_duration_pending.discard(url)

        threading.Thread(target=worker, daemon=True).start()

    def _trigger_media_action(self, action: str) -> None:
        run_script_bg("mpris.sh", action)
        self._schedule_media_refresh()

    def _schedule_media_refresh(self) -> None:
        self._poll_media_metadata()
        self._poll_media_progress()
        for delay in (150, 450, 900):
            QTimer.singleShot(delay, self._poll_media_metadata)
            QTimer.singleShot(delay, self._poll_media_progress)

    def _poll_media_progress(self) -> None:
        if not hasattr(self, "elapsed"):
            return
        player = self._media_player or run_script("mpris.sh", "player")
        if not player:
            self._media_position_ms = 0
            self._media_duration_ms = 0
            self._media_estimated_progress = False
            self._render_media_progress()
            return

        now = monotonic()
        elapsed_since_sync = max(0.0, now - self._media_last_sync)
        self._media_last_sync = now

        status_raw = (
            run_cmd(["playerctl", f"--player={player}", "status"]) or self._media_status
        )
        position_raw = run_cmd(["playerctl", f"--player={player}", "position"])
        length_raw = run_cmd(
            [
                "playerctl",
                f"--player={player}",
                "metadata",
                "--format",
                "{{mpris:length}}",
            ]
        )

        try:
            self._media_duration_ms = int(int(length_raw) / 1000)
        except Exception:
            self._media_duration_ms = 0

        if self._is_browser_player(player):
            url_duration_ms = self._media_duration_cache.get(self._media_url)
            if url_duration_ms is not None:
                self._media_duration_ms = url_duration_ms
            else:
                self._request_media_url_duration(self._media_url)

        parsed_position_ms: int | None = None
        try:
            parsed_position_ms = int(float(position_raw) * 1000)
        except Exception:
            parsed_position_ms = None

        if (
            parsed_position_ms is not None
            and self._media_duration_ms > 0
            and self._is_browser_player(player)
            and parsed_position_ms >= self._media_duration_ms - 1000
            and status_raw in {"Playing", "Paused"}
        ):
            self._media_estimated_progress = True
            parsed_position_ms = None
        elif parsed_position_ms is not None:
            self._media_estimated_progress = False

        if parsed_position_ms is not None:
            self._media_position_ms = max(0, parsed_position_ms)
        elif status_raw == "Playing" and self._media_duration_ms > 0:
            self._media_position_ms = min(
                self._media_duration_ms,
                max(0, self._media_position_ms + int(elapsed_since_sync * 1000)),
            )
        else:
            self._media_position_ms = max(0, self._media_position_ms)

        self._media_status = status_raw

        self._render_media_progress()

    def _render_media_progress(self) -> None:
        if not hasattr(self, "elapsed"):
            return
        self.elapsed.setText(format_millis(self._media_position_ms))
        self.total.setText(format_millis(self._media_duration_ms))

        track_width = self.progress_track.width() or 180
        if self._media_duration_ms > 0:
            ratio = max(
                0.0, min(1.0, self._media_position_ms / self._media_duration_ms)
            )
        else:
            ratio = 0.0
        fill_width = max(0, int(track_width * ratio))
        self.progress_fill.setGeometry(0, 0, fill_width, 4)

    def _queue_slider_commit(self, kind: str, value: int) -> None:
        if self._syncing_sliders:
            return
        if kind == "brightness":
            self._pending_brightness = value
            self._brightness_commit_timer.start(90)
        else:
            self._pending_volume = value
            self._volume_commit_timer.start(90)

    def _commit_brightness(self) -> None:
        run_script_bg("brightness.sh", "set", str(self._pending_brightness))

    def _commit_volume(self) -> None:
        run_script_bg("volume.sh", "set", str(self._pending_volume))

    def _set_cover_art(self, cover_path: Path) -> None:
        if not hasattr(self, "cover"):
            return
        pixmap = QPixmap(str(cover_path))
        if pixmap.isNull():
            self.cover.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            self.cover.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - self.cover.width()) // 2)
        y = max(0, (scaled.height() - self.cover.height()) // 2)
        cropped = scaled.copy(x, y, self.cover.width(), self.cover.height())

        rounded = QPixmap(self.cover.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.cover.width()), float(self.cover.height()), 16.0, 16.0
        )
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self.cover.setPixmap(rounded)

    def _update_media_palette_from_cover(self, cover_path: Path) -> None:
        if not hasattr(self, "media_base"):
            return
        palette = self._extract_cover_palette(cover_path)
        if palette is None:
            self._apply_media_palette()
            return
        self._apply_media_palette(*palette)

    def _extract_cover_palette(
        self, cover_path: Path
    ) -> tuple[str, str, str, str] | None:
        colors_raw = run_script("cover_colors.sh", "colors")
        colors = [color for color in colors_raw.split() if color.startswith("#")][:6]
        if len(colors) < 3:
            return None
        center = self._hex_to_rgba(colors[0], 0.26)
        mid = self._hex_to_rgba(colors[min(2, len(colors) - 1)], 0.58)
        border = self._darken_hex(colors[1], 0.12)
        accent = colors[min(4, len(colors) - 1)]
        return center, mid, border, accent

    def _hex_to_rgba(self, color: str, alpha: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return f"rgba(208, 188, 255, {alpha:.2f})"
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        return f"rgba({red}, {green}, {blue}, {alpha:.2f})"

    def _darken_hex(self, color: str, amount: float) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return "#4d4458"
        red = max(0, min(255, int(int(color[0:2], 16) * (1.0 - amount))))
        green = max(0, min(255, int(int(color[2:4], 16) * (1.0 - amount))))
        blue = max(0, min(255, int(int(color[4:6], 16) * (1.0 - amount))))
        return f"#{red:02X}{green:02X}{blue:02X}"

    def _profile_photo_path(self) -> Path | None:
        for candidate in PROFILE_PHOTO_CANDIDATES:
            if candidate.exists():
                return candidate
        return None

    def _rounded_avatar_pixmap(self, path: Path, size: int = 42) -> QPixmap:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size) // 2)
        y = max(0, (scaled.height() - size) // 2)
        cropped = scaled.copy(x, y, size, size)
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0.0, 0.0, float(size), float(size), 14.0, 14.0)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    def _refresh_profile_avatar(self, force: bool = False) -> None:
        if not hasattr(self, "avatar"):
            return
        photo_path = self._profile_photo_path()
        if photo_path is None:
            if force or self._avatar_source is not None:
                self.avatar.setPixmap(QPixmap())
                self.avatar.setText(material_icon("person"))
                self.avatar.setProperty("hasPhoto", False)
                self.avatar.style().unpolish(self.avatar)
                self.avatar.style().polish(self.avatar)
                self._avatar_source = None
                self._avatar_mtime_ns = -1
            return
        try:
            mtime_ns = photo_path.stat().st_mtime_ns
        except OSError:
            mtime_ns = -1
        if (
            not force
            and self._avatar_source == photo_path
            and self._avatar_mtime_ns == mtime_ns
        ):
            return
        rounded = self._rounded_avatar_pixmap(photo_path, self.avatar.width())
        if rounded.isNull():
            self.avatar.setPixmap(QPixmap())
            self.avatar.setText(material_icon("person"))
            self.avatar.setProperty("hasPhoto", False)
            self.avatar.style().unpolish(self.avatar)
            self.avatar.style().polish(self.avatar)
            return
        self.avatar.setText("")
        self.avatar.setPixmap(rounded)
        self.avatar.setProperty("hasPhoto", True)
        self.avatar.style().unpolish(self.avatar)
        self.avatar.style().polish(self.avatar)
        self._avatar_source = photo_path
        self._avatar_mtime_ns = mtime_ns

    def _open_profile_photo_picker(self) -> None:
        run_script_bg("chpfp.sh")
        for delay in (1200, 3000, 7000):
            QTimer.singleShot(
                delay, lambda force=True: self._refresh_profile_avatar(force=force)
            )

    def _open_settings(self) -> None:
        self._launch_settings_page("overview")

    def _show_overview_page(self) -> None:
        self._apply_window_mode("compact")
        self.page_stack.setCurrentWidget(self.overview_page)

    def _show_settings_section(self, key: str) -> None:
        if not hasattr(self, "settings_stack") or not self.settings_nav_buttons:
            self._launch_settings_page(
                key if key in {"overview", "appearance"} else "services"
            )
            return
        order = {"overview": 0, "appearance": 1, "homeassistant": 2}
        self.settings_stack.setCurrentIndex(order.get(key, 0))
        for button_key, button in self.settings_nav_buttons.items():
            button.apply_state(
                button_key == key,
                self.current_accent["accent"],
                self.current_accent["on_accent"],
                self.theme_palette,
            )

    def _open_settings_homeassistant(self) -> None:
        self._launch_settings_page("services")

    def _open_powermenu(self) -> None:
        if not POWERMENU_SCRIPT.exists():
            return
        run_bg_singleton(POWERMENU_SCRIPT)
        self.hide()

    def _launch_settings_page(self, page: str, service_section: str = "") -> None:
        if not SETTINGS_PAGE_SCRIPT.exists():
            return
        args = ["--page", page]
        if service_section:
            args.extend(["--service-section", service_section])
        for pattern in entry_patterns(SETTINGS_PAGE_SCRIPT):
            terminate_background_matches(pattern)
        try:
            subprocess.Popen(
                [python_executable(), str(SETTINGS_PAGE_SCRIPT), *args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            return
        self.hide()

    def _set_accent(self, key: str) -> None:
        self.settings_state["appearance"]["accent"] = key
        self.current_accent = accent_palette(key)
        save_notification_settings(self.settings_state)
        if self.appearance_status is not None:
            self.appearance_status.setText(f"Accent updated to {key.title()}.")
        self._apply_styles()
        self._apply_media_palette()
        if hasattr(self, "settings_stack"):
            self._show_settings_section("appearance")

    def _save_home_assistant_settings(self) -> None:
        if self.ha_url_input is None or self.ha_token_input is None:
            self._launch_settings_page("services")
            return
        self.settings_state["home_assistant"]["url"] = normalize_ha_url(
            self.ha_url_input.text()
        )
        self.settings_state["home_assistant"]["token"] = (
            self.ha_token_input.text().strip()
        )
        save_notification_settings(self.settings_state)
        if self.ha_settings_status is not None:
            self.ha_settings_status.setText("Home Assistant settings saved.")
        self._refresh_home_assistant_entities()

    def _refresh_home_assistant_entities(self) -> None:
        if not self._service_visible_in_notification_center("home_assistant"):
            self._ha_entities = []
            self._ha_entity_map = {}
            self._render_home_assistant_tiles()
            return
        base_url = normalize_ha_url(
            self.settings_state["home_assistant"].get("url", "")
        )
        token = self.settings_state["home_assistant"].get("token", "")
        payload, error_text = fetch_home_assistant_json(base_url, token, "/api/states")
        self._ha_last_error = error_text
        if error_text or not isinstance(payload, list):
            if self.ha_summary_label is not None:
                self.ha_summary_label.setText("")
            if self.ha_status_label is not None:
                self.ha_status_label.setText(error_text or "No entities available.")
            if self.ha_settings_status is not None:
                self.ha_settings_status.setText(
                    error_text or "Unable to fetch entities."
                )
            self._ha_entities = []
            self._ha_entity_map = {}
            self._rebuild_ha_entity_list()
            self._render_home_assistant_tiles()
            return
        self._ha_entities = sorted(
            [item for item in payload if isinstance(item, dict)],
            key=lambda item: str(item.get("entity_id", "")),
        )
        self._ha_entity_map = {
            str(item.get("entity_id", "")): item for item in self._ha_entities
        }
        if self.ha_summary_label is not None:
            self.ha_summary_label.setText("")
        if self.ha_status_label is not None:
            self.ha_status_label.setText("Pinned entity controls are live.")
        if self.ha_settings_status is not None:
            self.ha_settings_status.setText("Entities loaded successfully.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()

    def _rebuild_ha_entity_list(self) -> None:
        if not hasattr(self, "ha_entity_layout"):
            return
        while self.ha_entity_layout.count():
            item = self.ha_entity_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        pinned = set(self.settings_state["home_assistant"].get("pinned_entities", []))
        if not self._ha_entities:
            empty = QLabel("No Home Assistant entities to display.")
            empty.setObjectName("statusHint")
            self.ha_entity_layout.addWidget(empty)
            self.ha_entity_layout.addStretch(1)
            return
        for entity in self._ha_entities[:80]:
            entity_id = str(entity.get("entity_id", ""))
            state = str(entity.get("state", "unknown"))
            attrs = entity.get("attributes", {}) or {}
            name = str(attrs.get("friendly_name", entity_id))
            row = QFrame()
            row.setObjectName("metricCard")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(2)
            title = QLabel(name)
            title.setObjectName("metricValue")
            subtitle = QLabel(f"{entity_id} • {state}")
            subtitle.setObjectName("statusHint")
            text.addWidget(title)
            text.addWidget(subtitle)
            layout.addLayout(text, 1)
            pin_button = self._soft_button("Unpin" if entity_id in pinned else "Pin")
            pin_button.clicked.connect(
                lambda checked=False, current=entity_id: self._toggle_pin_entity(
                    current
                )
            )
            layout.addWidget(pin_button)
            self.ha_entity_layout.addWidget(row)
        self.ha_entity_layout.addStretch(1)

    def _toggle_pin_entity(self, entity_id: str) -> None:
        pinned = list(self.settings_state["home_assistant"].get("pinned_entities", []))
        if entity_id in pinned:
            pinned.remove(entity_id)
        else:
            if len(pinned) >= 5:
                self.ha_settings_status.setText("You can pin up to five entities.")
                return
            pinned.append(entity_id)
        self.settings_state["home_assistant"]["pinned_entities"] = pinned
        save_notification_settings(self.settings_state)
        self.ha_settings_status.setText(f"{len(pinned)}/5 entities pinned.")
        self._rebuild_ha_entity_list()
        self._render_home_assistant_tiles()

    def _render_home_assistant_tiles(self) -> None:
        self._sync_service_card_visibility()
        if not self._service_visible_in_notification_center("home_assistant"):
            return
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        for index, tile in enumerate(self.ha_action_tiles):
            if index >= len(pinned):
                tile.set_content("hub", "", "")
                tile.setProperty("entity_id", "")
                tile.setEnabled(False)
                continue
            entity_id = pinned[index]
            entity = self._ha_entity_map.get(entity_id, {})
            attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
            name = str(attrs.get("friendly_name", entity_id))
            state = (
                str(entity.get("state", "Unavailable"))
                if isinstance(entity, dict)
                else "Unavailable"
            )
            domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
            icon_name = {
                "light": "lightbulb",
                "switch": "tune",
                "climate": "thermostat",
                "camera": "camera_alt",
            }.get(domain, "home")
            tile.set_content(icon_name, name[:12], state[:12])
            tile.setEnabled(True)
            tile.setProperty("entity_id", entity_id)
        self.ha_card.setVisible(True)

    def _activate_ha_tile(self, index: int) -> None:
        pinned = self.settings_state["home_assistant"].get("pinned_entities", [])
        if index >= len(pinned):
            self._open_settings_homeassistant()
            return
        entity_id = pinned[index]
        entity = self._ha_entity_map.get(entity_id)
        if not entity:
            self.ha_status_label.setText("Entity state is not loaded yet.")
            return
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        state = str(entity.get("state", ""))
        service_domain = domain
        service = ""
        payload = {"entity_id": entity_id}
        if domain in {"light", "switch", "input_boolean"}:
            service = "turn_off" if state == "on" else "turn_on"
        elif domain == "scene":
            service = "turn_on"
            service_domain = "scene"
        elif domain == "script":
            service = "turn_on"
            service_domain = "script"
        else:
            self.ha_status_label.setText(f"{entity_id} is view-only right now.")
            return
        _, error_text = post_home_assistant_json(
            self.settings_state["home_assistant"].get("url", ""),
            self.settings_state["home_assistant"].get("token", ""),
            f"/api/services/{service_domain}/{service}",
            payload,
        )
        self.ha_status_label.setText(
            error_text or f"Triggered {service} for {entity_id}."
        )
        QTimer.singleShot(900, self._refresh_home_assistant_entities)

    def _toggle_wifi(self) -> None:
        run_script_bg("network.sh", "toggle")
        QTimer.singleShot(
            300,
            lambda: self._refresh_quick_settings_and_notify(
                "wifi",
                "Wi-Fi",
                "Wi-Fi connected",
                "Wi-Fi disconnected",
                WIFI_NOTIFICATION_ICON
                if Path(WIFI_NOTIFICATION_ICON).exists()
                else "network-wireless",
            ),
        )

    def _toggle_bluetooth(self) -> None:
        run_script_bg("bluetooth", "toggle")
        QTimer.singleShot(
            300,
            lambda: self._refresh_quick_settings_and_notify(
                "bluetooth",
                "Bluetooth",
                "Bluetooth enabled",
                "Bluetooth disabled",
                BLUETOOTH_NOTIFICATION_ICON
                if Path(BLUETOOTH_NOTIFICATION_ICON).exists()
                else "bluetooth",
            ),
        )

    def _toggle_airplane(self) -> None:
        run_script_bg("network.sh", "toggle-radio")
        QTimer.singleShot(
            300,
            lambda: self._refresh_quick_settings_and_notify(
                "airplane",
                "Airplane Mode",
                "Airplane mode enabled",
                "Airplane mode disabled",
                AIRPLANE_NOTIFICATION_ICON
                if Path(AIRPLANE_NOTIFICATION_ICON).exists()
                else "airplane-mode-symbolic",
            ),
        )

    def _toggle_night(self) -> None:
        run_script_bg("redshift", "toggle")
        QTimer.singleShot(
            300,
            lambda: self._refresh_quick_settings_and_notify(
                "night",
                "Night Light",
                "Night light enabled",
                "Night light disabled",
                NIGHT_LIGHT_NOTIFICATION_ICON
                if Path(NIGHT_LIGHT_NOTIFICATION_ICON).exists()
                else "nightlight",
            ),
        )

    def _toggle_caffeine(self) -> None:
        caffeine_script = SCRIPTS_DIR / "caffeine.sh"
        if caffeine_script.exists():
            run_bg(["env", "HANAUTA_QUIET=1", str(caffeine_script), "toggle"])
        QTimer.singleShot(
            300,
            lambda: self._refresh_quick_settings_and_notify(
                "caffeine",
                "Caffeine",
                "Caffeine enabled",
                "Caffeine disabled",
                CAFFEINE_NOTIFICATION_ICON
                if Path(CAFFEINE_NOTIFICATION_ICON).exists()
                else "coffee",
            ),
        )

    def _toggle_dnd(self) -> None:
        dnd_on = parse_bool_text(run_cmd(notification_control_command("is-paused")))
        if dnd_on:
            run_cmd(notification_control_command("set-paused", "false"))
            run_bg(
                [
                    "notify-send",
                    "Notifications",
                    "Notifications are now globally enabled",
                ]
            )
            QTimer.singleShot(150, self._poll_quick_settings)
            return

        run_bg(
            [
                "notify-send",
                "Do Not Disturb",
                "This is the last desktop notification. Notifications will now be globally disabled.",
            ]
        )
        QTimer.singleShot(350, self._enable_dnd_after_warning)

    def _enable_dnd_after_warning(self) -> None:
        run_cmd(notification_control_command("set-paused", "true"))
        self._poll_quick_settings()

    def _show_system_notification(
        self, title: str, body: str, icon_name: str = ""
    ) -> None:
        run_bg(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.freedesktop.Notifications",
                "--object-path",
                "/org/freedesktop/Notifications",
                "--method",
                "org.freedesktop.Notifications.Notify",
                "Hanauta",
                "0",
                icon_name,
                title,
                body,
                "[]",
                "{}",
                "3000",
            ]
        )

    def _refresh_quick_settings_and_notify(
        self,
        key: str,
        title: str,
        enabled_message: str,
        disabled_message: str,
        icon_name: str,
    ) -> None:
        self._poll_quick_settings()
        button = self.quick_buttons.get(key)
        if button is None:
            return
        self._show_system_notification(
            title,
            enabled_message if button.active else disabled_message,
            icon_name,
        )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(rgba(self.theme_palette.panel_border, 0.92)), 1))
        painter.setBrush(QColor(rgba(self.theme_palette.panel_bg, 0.96)))
        painter.drawRoundedRect(rect, 28, 28)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._sync_media_card_layers()
        self._render_media_progress()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Control Center")
    window = NotificationCenter()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
