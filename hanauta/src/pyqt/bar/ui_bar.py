#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyberBar - compact PyQt6 top bar aligned with the bar idea mock.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import html
import imaplib
import json
import math
import os
import re
import shutil
import sqlite3
import ssl
import subprocess
import sys
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote, unquote

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from PyQt6.QtCore import (
    QByteArray,
    QEasingCurve,
    QFileSystemWatcher,
    QObject,
    QPoint,
    QProcess,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QThread,
    pyqtClassInfo,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPalette,
    QPixmap,
    QRegion,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from pyqt.shared.runtime import (
    entry_command,
    entry_patterns,
    entry_target,
    fonts_root,
    hanauta_root,
    project_root,
    python_executable,
    scripts_root,
    source_root,
)
from pyqt.shared.plugin_bridge import (
    build_polkit_command,
    polkit_available,
    run_with_polkit,
    trigger_fullscreen_alert,
)
from pyqt.shared.plugin_runtime import resolve_plugin_script
from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba, theme_font_family

def _load_plugin_backend(module_name: str, candidates: list[Path]) -> Any:
    for candidate in candidates:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"Unable to load plugin backend {module_name}: {candidates}")


_RSS_BACKEND = _load_plugin_backend(
    "hanauta_plugin_rss_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-rss" / "rss_backend.py",
    ],
)
collect_rss_entries = _RSS_BACKEND.collect_entries
rss_entry_fingerprint = _RSS_BACKEND.entry_fingerprint
load_rss_cache = _RSS_BACKEND.load_cache
save_rss_cache = _RSS_BACKEND.save_cache

_CAP_ALERTS_BACKEND = _load_plugin_backend(
    "hanauta_plugin_cap_alerts_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-cap-alerts" / "cap_alerts_shared.py",
    ],
)
CapAlert = _CAP_ALERTS_BACKEND.CapAlert
alert_accent_color = _CAP_ALERTS_BACKEND.alert_accent_color
configured_alert_location = _CAP_ALERTS_BACKEND.configured_alert_location
fallback_tip = _CAP_ALERTS_BACKEND.fallback_tip
fetch_active_alerts = _CAP_ALERTS_BACKEND.fetch_active_alerts
relative_expiry = _CAP_ALERTS_BACKEND.relative_expiry
test_mode_enabled = _CAP_ALERTS_BACKEND.test_mode_enabled
top_alert = _CAP_ALERTS_BACKEND.top_alert

_WEATHER_BACKEND = _load_plugin_backend(
    "hanauta_plugin_weather_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-weather" / "weather_backend.py",
    ],
)
AnimatedWeatherIcon = _WEATHER_BACKEND.AnimatedWeatherIcon
WeatherForecast = _WEATHER_BACKEND.WeatherForecast
animated_icon_path = _WEATHER_BACKEND.animated_icon_path
configured_city = _WEATHER_BACKEND.configured_city
fetch_forecast = _WEATHER_BACKEND.fetch_forecast
weather_condition_label = _WEATHER_BACKEND.weather_condition_label

_UPDATES_BACKEND = _load_plugin_backend(
    "hanauta_plugin_updates_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-updates" / "updates_backend.py",
    ],
)
collect_update_payload = _UPDATES_BACKEND.collect_update_payload

_HEALTH_BACKEND = _load_plugin_backend(
    "hanauta_plugin_health_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-health" / "health_backend.py",
    ],
)
format_steps_short = _HEALTH_BACKEND.format_steps_short
health_tooltip = _HEALTH_BACKEND.health_tooltip
load_current_snapshot = _HEALTH_BACKEND.load_current_snapshot
load_health_service_settings = _HEALTH_BACKEND.load_health_service_settings
poll_health_reminders = _HEALTH_BACKEND.poll_health_reminders

_CRYPTO_BACKEND = _load_plugin_backend(
    "hanauta_plugin_crypto_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-crypto" / "crypto_backend.py",
    ],
)
build_crypto_price_alerts = _CRYPTO_BACKEND.build_price_alerts
fetch_crypto_prices = _CRYPTO_BACKEND.fetch_prices
load_crypto_settings_state = _CRYPTO_BACKEND.load_settings_state
load_crypto_tracker_state = _CRYPTO_BACKEND.load_tracker_state
crypto_movement_summary = _CRYPTO_BACKEND.movement_summary
save_crypto_tracker_state = _CRYPTO_BACKEND.save_tracker_state
crypto_should_check = _CRYPTO_BACKEND.should_check
crypto_slug_to_name = _CRYPTO_BACKEND.slug_to_name

_GAMEMODE_BACKEND = _load_plugin_backend(
    "hanauta_plugin_gamemode_backend",
    [
        Path.home() / "dev" / "hanauta-plugin-game-mode" / "gamemode_backend.py",
    ],
)
game_mode_service_enabled = _GAMEMODE_BACKEND.service_enabled
game_mode_summary = _GAMEMODE_BACKEND.summary

APP_DIR = source_root()
ROOT = project_root()
REPO_ROOT = project_root()
HANAUTA_ROOT = hanauta_root()
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

NOTIFICATION_CENTER = (
    APP_DIR / "pyqt" / "notification-center" / "notification_center.py"
)
AI_POPUP: Path | None = resolve_plugin_script("ai_popup.py", ["ai-popup"])
WIFI_CONTROL_PY: Path | None = resolve_plugin_script(
    "wifi_control.py", ["wifi-control", "wifi"]
)
WIFI_CONTROL_BINARY = HANAUTA_ROOT / "bin" / "hanauta-wifi-control"
WIFI_CONTROL = WIFI_CONTROL_PY
VPN_CONTROL: Path | None = resolve_plugin_script(
    "vpn_control.py", ["vpn-control", "vpn"]
)
CHRISTIAN_WIDGET: Path | None = resolve_plugin_script(
    "christian_widget.py", ["religion-christian", "christian"]
)
HEALTH_WIDGET: Path | None = resolve_plugin_script("health_widget.py", ["health"])
REMINDERS_WIDGET: Path | None = resolve_plugin_script(
    "reminders_widget.py", ["reminders"]
)
POMODORO_WIDGET: Path | None = resolve_plugin_script("pomodoro_widget.py", ["pomodoro"])
RSS_WIDGET: Path | None = resolve_plugin_script("rss_widget.py", ["rss"])
POWERMENU_WIDGET = APP_DIR / "pyqt" / "powermenu" / "powermenu.py"
OBS_WIDGET: Path | None = resolve_plugin_script("obs_widget.py", ["obs"])
OBS_STATUS: Path | None = resolve_plugin_script("obs_status.py", ["obs"])
UPDATES_WIDGET: Path | None = resolve_plugin_script("updates_widget.py", ["updates"])
CRYPTO_WIDGET: Path | None = resolve_plugin_script("crypto_widget.py", ["crypto"])
VPS_WIDGET: Path | None = resolve_plugin_script("vps_widget.py", ["vps"])


def _resolve_desktop_clock_widget() -> Path | None:
    resolved = resolve_plugin_script("desktop_clock_widget.py", ["desktop-clock", "clock"])
    if resolved is not None and resolved.exists():
        return resolved
    fallback_candidates = (
        HANAUTA_ROOT / "src" / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py",
        Path.home() / "dev" / "hanauta-plugin-desktop-clock" / "desktop_clock_widget.py",
    )
    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate
    return None


DESKTOP_CLOCK_WIDGET: Path | None = _resolve_desktop_clock_widget()
DESKTOP_CLOCK_BINARY = HANAUTA_ROOT / "bin" / "hanauta-clock"
NTFY_POPUP: Path | None = resolve_plugin_script("ntfy_popup.py", ["ntfy"])
WEATHER_POPUP: Path | None = resolve_plugin_script(
    "weather_popup.py", ["weather"], required=False
)
CAP_ALERTS_POPUP: Path | None = resolve_plugin_script(
    "cap_alerts_popup.py", ["cap-alerts", "alerts"]
)
CAP_ALERTS_OVERLAY: Path | None = resolve_plugin_script(
    "cap_alert_overlay.py", ["cap-alerts", "alerts"]
)
CALENDAR_POPUP: Path | None = resolve_plugin_script("calendar_popup.py", ["calendar"])
GAME_MODE_POPUP: Path | None = resolve_plugin_script(
    "game_mode_popup.py", ["game-mode", "gamemode"]
)
SETTINGS_PAGE = APP_DIR / "pyqt" / "settings-page" / "settings.py"
ACTION_NOTIFICATION_SCRIPT = APP_DIR / "pyqt" / "shared" / "action_notification.py"
LAUNCHER_APP = APP_DIR / "pyqt" / "launcher" / "launcher.py"
CAVA_BAR_CONFIG = APP_DIR / "pyqt" / "bar" / "cava_bar.conf"
STATUS_NOTIFIER_WATCHER = APP_DIR / "pyqt" / "bar" / "status_notifier_watcher.py"
EMAIL_CLIENT: Path | None = resolve_plugin_script(
    "email_client.py", ["email-client", "mail"]
)
OPEN_MAIL_MESSAGE = APP_DIR / "pyqt" / "shared" / "open_mail_message.py"
SCRIPTS_DIR = scripts_root()
LAUNCHER_SCRIPT = SCRIPTS_DIR / "open_launcher.sh"
FONTS_DIR = fonts_root()
ASSETS_DIR = source_root() / "assets"
VPN_ICON_ON = ASSETS_DIR / "vpn_key.svg"
VPN_ICON_OFF = ASSETS_DIR / "vpn_key_off.svg"
CHRISTIAN_ICON = ASSETS_DIR / "cath.svg"
OBS_ICON = ASSETS_DIR / "OBS Studio.svg"
OBS_STREAMING_ACTIVE_ICON = ASSETS_DIR / "obs-streaming-active.svg"
OBS_STREAMING_INACTIVE_ICON = ASSETS_DIR / "obs-streaming-inactive.svg"
OBS_RECORDING_ACTIVE_ICON = ASSETS_DIR / "obs-recording-active.svg"
OBS_RECORDING_INACTIVE_ICON = ASSETS_DIR / "obs-recording-inactive.svg"
RSS_ICON = ASSETS_DIR / "rss-feed.svg"
REMINDER_ICON = ASSETS_DIR / "reminder-widget.svg"
POMODORO_ICON = ASSETS_DIR / "pomodoro.svg"
NTFY_ICON = ASSETS_DIR / "ntfy.svg"
CLIPBOARD_ICON = ASSETS_DIR / "clipboard.svg"
GAME_MODE_ICON = ASSETS_DIR / "game-mode.svg"
CRYPTO_ICON = ASSETS_DIR / "bitcoin.svg"
SETTINGS_FILE = (
    Path.home()
    / ".local"
    / "state"
    / "hanauta"
    / "notification-center"
    / "settings.json"
)
BAR_ICON_CONFIG_DIR = Path.home() / ".config" / "hanauta"
BAR_ICON_CONFIG_FILE = BAR_ICON_CONFIG_DIR / "bar-icons.json"
BAR_ICON_EXAMPLE_FILE = ROOT / "hanauta" / "config" / "bar-icons.example.json"
MAIL_STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "email-client"
MAIL_STORAGE_CONFIG_PATH = MAIL_STATE_DIR / "storage.json"
MAIL_DB_PATH = MAIL_STATE_DIR / "mail.sqlite3"
LOCKSTATUS_SCRIPT = SCRIPTS_DIR / "lockstatus.sh"
TRAY_SLOT_WIDTH = 24
TRAY_SLOT_HEIGHT = 32
TRAY_SLOT_SIZE = 20
TRAY_ICON_SIZE = 16
MAIL_NOTIFICATION_ACTION_KEY = "hanauta-mail-read"
MAIL_NOTIFICATION_TIMEOUT_MS = 15000
BAR_PLUGIN_ENTRYPOINT = "hanauta_bar_plugin.py"
HOST_PLUGIN_API_VERSION = 1
PLUGIN_DEV_ROOT = Path.home() / "dev"
HAS_DBUS_NEXT = importlib.util.find_spec("dbus_next") is not None
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
if not HAS_DBUS_NEXT:
    logger.warning(
        "dbus_next is not installed; action notifications will fall back to notify-send."
    )

MATERIAL_ICONS = {
    "battery_2_bar": "\uebe0",
    "battery_3_bar": "\uebdd",
    "battery_5_bar": "\uebd4",
    "battery_alert": "\ue19c",
    "battery_charging_full": "\ue1a3",
    "battery_full": "\ue1a4",
    "auto_awesome": "\ue65f",
    "bluetooth": "\ue1a7",
    "coffee": "\uefef",
    "content_paste": "\ue14f",
    "md-bitcoin": "\uebc5",
    "currency_bitcoin": "\uebc5",
    "dashboard": "\ue871",
    "home": "\ue88a",
    "mail": "\ue158",
    "music_note": "\ue405",
    "notifications": "\ue7f4",
    "notifications_active": "\ue7f7",
    "pause": "\ue034",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "public": "\ue80b",
    "warning": "\ue002",
    "videocam": "\ue04b",
    "show_chart": "\ue6e1",
    "timer": "\ue425",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "system_update": "\ue62a",
    "favorite": "\ue87d",
    "shield": "\ue9e0",
    "trip_origin": "\ue57b",
    "vpn_key": "\ue0da",
    "wifi": "\ue63e",
    "wifi_off": "\ue648",
    "sports_esports": "\uea28",
    "school": "\ue80c",
    "expand_more": "\ue5cf",
    "expand_less": "\ue5ce",
}
MONITOR_MODE_PRIMARY = "primary"
MONITOR_MODE_FOLLOW_MOUSE = "follow_mouse"
MONITOR_MODE_NAMED = "named"

REMINDERS_BAR_GLYPH = "\ue003"


DEFAULT_BAR_SETTINGS = {
    "launcher_offset": 0,
    "workspace_offset": 0,
    "workspace_count": 5,
    "show_workspace_label": False,
    "datetime_offset": 0,
    "media_offset": 0,
    "status_offset": 0,
    "tray_offset": 0,
    "status_icon_limit": 14,
    "bar_height": 45,
    "chip_radius": 0,
    "tray_tint_with_matugen": True,
    "use_color_widget_icons": False,
    "debug_tooltips": False,
    "merge_all_chips": False,
    "full_bar_radius": 18,
    "orientation_mode": "horizontal_top",
    "monitor_mode": MONITOR_MODE_PRIMARY,
    "monitor_name": "",
    "service_icon_order": [],
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
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return ""
    return run_cmd([str(script_path), *args])


def run_script_bg(script_name: str, *args: str) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return
    run_bg([str(script_path), *args])


def run_bg_detached(cmd: list[str]) -> bool:
    if not cmd:
        return False
    try:
        if QProcess.startDetached(cmd[0], cmd[1:]):
            return True
    except Exception:
        pass
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def run_bg(cmd: list[str]) -> None:
    run_bg_detached(cmd)


def action_notifications_supported() -> bool:
    return ACTION_NOTIFICATION_SCRIPT.exists() and HAS_DBUS_NEXT


def antialias_font(font: QFont) -> QFont:
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def apply_antialias_font(widget: QWidget) -> None:
    widget.setFont(antialias_font(widget.font()))
    for child in widget.findChildren(QWidget):
        child.setFont(antialias_font(child.font()))


def widget_python() -> str:
    return python_executable()


def terminate_background_matches(pattern: str) -> None:
    try:
        subprocess.run(
            ["pkill", "-f", re.escape(pattern)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def background_match_exists(pattern: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", re.escape(pattern)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def focused_workspace_name() -> str:
    raw = run_cmd(["i3-msg", "-t", "get_workspaces"])
    if not raw:
        return ""
    try:
        workspaces = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(workspaces, list):
        return ""
    for item in workspaces:
        if isinstance(item, dict) and bool(item.get("focused", False)):
            return str(item.get("name", "")).strip()
    return ""


def _screen_matches_output(screen: QScreen, output_name: str) -> bool:
    screen_name = screen.name().strip()
    return bool(screen_name) and screen_name == output_name.strip()


def _active_output_names() -> tuple[str, str]:
    primary_output_name = ""
    fallback_output_name = ""
    raw = run_cmd(["i3-msg", "-t", "get_outputs"])
    if not raw:
        return primary_output_name, fallback_output_name
    try:
        outputs = json.loads(raw)
    except Exception:
        return primary_output_name, fallback_output_name
    if not isinstance(outputs, list):
        return primary_output_name, fallback_output_name
    for item in outputs:
        if not isinstance(item, dict) or not bool(item.get("active", False)):
            continue
        output_name = str(item.get("name", "")).strip()
        if not output_name:
            continue
        if not fallback_output_name:
            fallback_output_name = output_name
        if bool(item.get("primary", False)):
            primary_output_name = output_name
            break
    return primary_output_name, fallback_output_name


def _screen_by_name(output_name: str) -> QScreen | None:
    target_name = output_name.strip()
    if not target_name:
        return None
    for screen in QApplication.screens():
        if _screen_matches_output(screen, target_name):
            return screen
    return None


def preferred_bar_screen(
    monitor_mode: str = MONITOR_MODE_PRIMARY, monitor_name: str = ""
) -> QScreen | None:
    screens = QApplication.screens()
    if not screens:
        return None

    normalized_mode = str(monitor_mode or MONITOR_MODE_PRIMARY).strip().lower()
    if normalized_mode == MONITOR_MODE_FOLLOW_MOUSE:
        screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is not None:
            return screen
        normalized_mode = MONITOR_MODE_PRIMARY
    elif normalized_mode == MONITOR_MODE_NAMED:
        screen = _screen_by_name(monitor_name)
        if screen is not None:
            return screen
        normalized_mode = MONITOR_MODE_PRIMARY

    primary_output_name, fallback_output_name = _active_output_names()
    for output_name in (primary_output_name, fallback_output_name):
        screen = _screen_by_name(output_name)
        if screen is not None:
            return screen

    primary_screen = QApplication.primaryScreen()
    if primary_screen is not None:
        return primary_screen
    return screens[0]


def _collect_leaf_windows(node: dict, visible_windows: list[dict]) -> None:
    if not isinstance(node, dict):
        return
    nodes = node.get("nodes", [])
    floating_nodes = node.get("floating_nodes", [])
    if isinstance(nodes, list):
        for child in nodes:
            _collect_leaf_windows(child, visible_windows)
    if isinstance(floating_nodes, list):
        for child in floating_nodes:
            _collect_leaf_windows(child, visible_windows)
    if node.get("window"):
        visible_windows.append(node)


def focused_workspace_has_real_windows() -> bool:
    workspace_raw = run_cmd(["i3-msg", "-t", "get_workspaces"], timeout=2.0)
    tree_raw = run_cmd(["i3-msg", "-t", "get_tree"], timeout=3.0)
    if not workspace_raw or not tree_raw:
        return False
    try:
        workspaces = json.loads(workspace_raw)
        tree = json.loads(tree_raw)
    except Exception:
        return False
    if not isinstance(workspaces, list):
        return False
    current_workspace = ""
    for item in workspaces:
        if isinstance(item, dict) and bool(item.get("focused", False)):
            current_workspace = str(item.get("name", "")).strip()
            break
    if not current_workspace:
        return False

    def find_workspace(node: dict) -> dict | None:
        if not isinstance(node, dict):
            return None
        if (
            node.get("type") == "workspace"
            and str(node.get("name", "")).strip() == current_workspace
        ):
            return node
        for key in ("nodes", "floating_nodes"):
            children = node.get(key, [])
            if not isinstance(children, list):
                continue
            for child in children:
                found = find_workspace(child)
                if found is not None:
                    return found
        return None

    workspace = find_workspace(tree)
    if workspace is None:
        return False
    windows: list[dict] = []
    _collect_leaf_windows(workspace, windows)
    ignored_classes = {
        "CyberBar",
        "CyberDock",
        "HanautaDesktopClock",
        "HanautaClock",
        "HanautaHotkeys",
    }
    ignored_titles = {
        "CyberBar",
        "Hanauta Desktop Clock",
        "Hanauta Clock",
    }
    for item in windows:
        props = item.get("window_properties", {})
        if not isinstance(props, dict):
            props = {}
        wm_class = str(props.get("class", "")).strip()
        title = str(item.get("name", "")).strip()
        if wm_class in ignored_classes or title in ignored_titles:
            continue
        return True
    return False


def desktop_clock_target() -> Path | None:
    if DESKTOP_CLOCK_WIDGET is not None and DESKTOP_CLOCK_WIDGET.exists():
        return DESKTOP_CLOCK_WIDGET
    if DESKTOP_CLOCK_BINARY.exists():
        return DESKTOP_CLOCK_BINARY
    return None


def desktop_clock_command() -> list[str]:
    target = desktop_clock_target()
    if target is None:
        return []
    if target == DESKTOP_CLOCK_BINARY:
        return [str(target)]
    return entry_command(target)


def detect_font(*families: str) -> str:
    for family in families:
        if QFont(family).exactMatch():
            return family
    return "Sans Serif"


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def ensure_bar_icon_config() -> None:
    try:
        BAR_ICON_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not BAR_ICON_CONFIG_FILE.exists() and BAR_ICON_EXAMPLE_FILE.exists():
            BAR_ICON_CONFIG_FILE.write_text(
                BAR_ICON_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
            )
    except OSError:
        return


def load_bar_icon_overrides() -> dict[str, str]:
    ensure_bar_icon_config()
    try:
        payload = json.loads(BAR_ICON_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            result[key.strip()] = value.strip()
    return result


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "ui_sans": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "ui_display": FONTS_DIR / "Rubik-VariableFont_wght.ttf",
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "pomicons": FONTS_DIR / "Pomicons.ttf",
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


def _tint_pixmap_from_alpha(source: QPixmap, color: QColor) -> QPixmap:
    if source.isNull():
        return QPixmap()

    src = source.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    out = QImage(src.size(), QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.transparent)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # First paint the desired tint color everywhere...
    painter.fillRect(out.rect(), color)

    # ...then keep only the original alpha mask.
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, src)
    painter.end()

    return _drop_low_alpha_noise(QPixmap.fromImage(out))


def _render_svg_renderer(renderer: QSvgRenderer, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    return pixmap


def _resolve_param_svg_colors(raw_svg: str, color: QColor) -> str:
    color_hex = color.name(QColor.NameFormat.HexRgb)
    alpha_text = f"{color.alphaF():.3f}".rstrip("0").rstrip(".")
    if not alpha_text:
        alpha_text = "1"

    return (
        raw_svg.replace("param(fill)", color_hex)
        .replace("param(outline)", color_hex)
        .replace("param(fill-opacity)", alpha_text)
        .replace("param(outline-opacity)", alpha_text)
        .replace("param(outline-width)", "1.5")
    )


def tinted_svg_icon(path: Path, color: QColor, size: int = 16) -> QIcon:
    if not path.exists():
        return QIcon()

    try:
        raw_svg = path.read_text(encoding="utf-8")
    except OSError:
        raw_svg = ""

    renderer = QSvgRenderer()

    if raw_svg:
        # If the SVG uses param(fill)/param(outline), color it at SVG level.
        svg_text = (
            _resolve_param_svg_colors(raw_svg, color)
            if "param(" in raw_svg
            else raw_svg
        )
        renderer.load(QByteArray(svg_text.encode("utf-8")))
    else:
        renderer.load(str(path))

    if not renderer.isValid():
        return QIcon()

    pixmap = _render_svg_renderer(renderer, size)

    # For param-based symbolic SVGs, the SVG itself is already colored correctly.
    if raw_svg and "param(" in raw_svg:
        return QIcon(_drop_low_alpha_noise(pixmap))

    # For generic SVGs, tint using alpha only.
    return QIcon(_tint_pixmap_from_alpha(pixmap, color))


def tinted_raster_icon(path: Path, color: QColor, size: int = 16) -> QIcon:
    if not path.exists():
        return QIcon()

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QIcon()

    source = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QIcon(_tint_pixmap_from_alpha(source, color))


def native_svg_icon(path: Path, size: int = 16) -> QIcon:
    if not path.exists():
        return QIcon()
    icon = QIcon(str(path))
    if icon.isNull():
        return QIcon()
    pixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        return QIcon()
    return QIcon(pixmap)


def _drop_low_alpha_noise(pixmap: QPixmap, threshold: int = 24) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width = image.width()
    height = image.height()
    for y in range(height):
        for x in range(width):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() < threshold:
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))
            else:
                # Keep original anti-aliased alpha so tinted icons stay soft.
                image.setPixelColor(
                    x, y, QColor(pixel.red(), pixel.green(), pixel.blue(), pixel.alpha())
                )
    return QPixmap.fromImage(image)


def tinted_qicon(icon: QIcon, color: QColor, size: int = 16) -> QIcon:
    if icon.isNull():
        return QIcon()

    source = icon.pixmap(size, size)
    if source.isNull():
        return QIcon()

    return QIcon(_tint_pixmap_from_alpha(source, color))


def load_service_settings() -> dict[str, dict[str, object]]:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    services = payload.get("services", {})
    return services if isinstance(services, dict) else {}


def discover_bar_plugin_entrypoints() -> list[Path]:
    settings = load_runtime_settings()
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    installed = (
        marketplace.get("installed_plugins", [])
        if isinstance(marketplace, dict)
        else []
    )
    entrypoints: list[Path] = []
    seen: set[str] = set()
    if isinstance(installed, list):
        for row in installed:
            if not isinstance(row, dict):
                continue
            try:
                api_min_version = int(row.get("api_min_version", 1) or 1)
            except Exception:
                api_min_version = 1
            if max(1, api_min_version) > HOST_PLUGIN_API_VERSION:
                continue
            install_path = str(row.get("install_path", "")).strip()
            if not install_path:
                continue
            entrypoint = Path(install_path).expanduser() / BAR_PLUGIN_ENTRYPOINT
            if not entrypoint.exists():
                continue
            key = str(entrypoint.resolve())
            if key in seen:
                continue
            seen.add(key)
            entrypoints.append(entrypoint)

    install_root = (
        Path(
            str(marketplace.get("install_dir", str(ROOT / "hanauta" / "plugins")))
        ).expanduser()
        if isinstance(marketplace, dict)
        else ROOT / "hanauta" / "plugins"
    )
    search_roots = [install_root, ROOT / "hanauta" / "plugins"]
    for root in search_roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            entrypoint = child / BAR_PLUGIN_ENTRYPOINT
            if not entrypoint.exists():
                continue
            key = str(entrypoint.resolve())
            if key in seen:
                continue
            seen.add(key)
            entrypoints.append(entrypoint)
    if PLUGIN_DEV_ROOT.exists() and PLUGIN_DEV_ROOT.is_dir():
        try:
            dev_children = sorted(PLUGIN_DEV_ROOT.iterdir())
        except OSError:
            dev_children = []
        for child in dev_children:
            if not child.is_dir():
                continue
            if not child.name.startswith("hanauta-plugin-"):
                continue
            entrypoint = child / BAR_PLUGIN_ENTRYPOINT
            if not entrypoint.exists():
                continue
            key = str(entrypoint.resolve())
            if key in seen:
                continue
            seen.add(key)
            entrypoints.append(entrypoint)
    return entrypoints


def resolve_rss_widget_script() -> Path | None:
    return RSS_WIDGET


def _theme_choice_for_icon_selection(settings: object) -> str:
    appearance = settings.get("appearance", {}) if isinstance(settings, dict) else {}
    appearance = appearance if isinstance(appearance, dict) else {}
    if bool(appearance.get("use_matugen_palette", False)):
        return "wallpaper_aware"
    choice = str(appearance.get("theme_choice", "")).strip().lower()
    if choice == "wallpaper-aware":
        return "wallpaper_aware"
    if choice:
        return choice
    fallback = str(appearance.get("theme_mode", "dark")).strip().lower()
    return fallback if fallback else "dark"


def _prefer_color_widget_icons(settings: object) -> bool:
    bar = settings.get("bar", {}) if isinstance(settings, dict) else {}
    bar = bar if isinstance(bar, dict) else {}
    return bool(bar.get("use_color_widget_icons", False))


def resolve_rss_icon_path(prefer_color: bool | None = None) -> Path:
    settings = load_runtime_settings()
    if prefer_color is None:
        prefer_color = _prefer_color_widget_icons(settings)
    script_path = resolve_rss_widget_script()
    if script_path is None or not script_path.exists():
        return RSS_ICON
    plugin_root = script_path.parent
    candidates = (
        [
            plugin_root / "assets" / "icon_color.svg",
            plugin_root / "icon_color.svg",
            plugin_root / "assets" / "icon.svg",
            plugin_root / "icon.svg",
        ]
        if prefer_color
        else [
            plugin_root / "assets" / "icon.svg",
            plugin_root / "icon.svg",
            plugin_root / "assets" / "icon_color.svg",
            plugin_root / "icon_color.svg",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return RSS_ICON


def resolve_ntfy_popup_script() -> Path | None:
    return NTFY_POPUP


def resolve_game_mode_icon_path(prefer_color: bool | None = None) -> Path:
    settings = load_runtime_settings()
    if prefer_color is None:
        prefer_color = _prefer_color_widget_icons(settings)
    script_path = GAME_MODE_POPUP
    if script_path is None or not script_path.exists():
        return GAME_MODE_ICON
    plugin_root = script_path.parent
    candidates = (
        [
            plugin_root / "assets" / "icon_color.svg",
            plugin_root / "icon_color.svg",
            plugin_root / "assets" / "icon.svg",
            plugin_root / "icon.svg",
        ]
        if prefer_color
        else [
            # In mono/tint mode, always start from the mono asset.
            plugin_root / "assets" / "icon.svg",
            plugin_root / "icon.svg",
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return GAME_MODE_ICON


def resolve_ntfy_icon_path(prefer_color: bool | None = None) -> Path:
    settings = load_runtime_settings()
    if prefer_color is None:
        prefer_color = _prefer_color_widget_icons(settings)
    marketplace = settings.get("marketplace", {}) if isinstance(settings, dict) else {}
    install_dir = str(marketplace.get("install_dir", "")).strip()
    roots: list[Path] = []
    if install_dir:
        roots.append(Path(install_dir).expanduser())
    roots.extend(
        [
            ROOT / "hanauta" / "plugins",
            Path.home() / ".config" / "i3" / "hanauta" / "plugins",
            PLUGIN_DEV_ROOT,
        ]
    )
    for root in roots:
        if not root.exists():
            continue
        if root.is_dir():
            children = (
                sorted(root.iterdir())
                if root != PLUGIN_DEV_ROOT
                else [root / "hanauta-plugin-ntfy"]
            )
            for child in children:
                if not child.exists() or not child.is_dir():
                    continue
                if "ntfy" not in child.name.lower():
                    continue
                color_icon = child / "assets" / "icon_color.svg"
                mono_icon = child / "assets" / "icon.svg"
                root_color = child / "icon_color.svg"
                root_mono = child / "icon.svg"
                candidates = (
                    [color_icon, root_color, mono_icon, root_mono]
                    if prefer_color
                    else [mono_icon, root_mono, color_icon, root_color]
                )
                for candidate in candidates:
                    if candidate.exists():
                        return candidate
    return NTFY_ICON


def load_runtime_settings() -> dict[str, object]:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def normalize_runtime_settings(payload: object) -> dict[str, object]:
    settings = payload if isinstance(payload, dict) else {}
    services = settings.get("services", {})
    settings["services"] = services if isinstance(services, dict) else {}
    return settings


def load_region_settings_from_payload(settings: object) -> dict[str, object]:
    current = settings.get("region", {}) if isinstance(settings, dict) else {}
    current = current if isinstance(current, dict) else {}
    date_style = str(current.get("date_style", "us")).strip().lower()
    temperature_unit = str(current.get("temperature_unit", "c")).strip().lower()
    return {
        "locale_code": str(current.get("locale_code", "")).strip(),
        "use_24_hour": bool(current.get("use_24_hour", False)),
        "date_style": date_style if date_style in {"us", "iso", "eu"} else "us",
        "temperature_unit": temperature_unit if temperature_unit in {"c", "f"} else "c",
    }


def load_bar_settings_from_payload(settings: object) -> dict[str, object]:
    current = settings.get("bar", {}) if isinstance(settings, dict) else {}
    current = current if isinstance(current, dict) else {}
    merged = dict(DEFAULT_BAR_SETTINGS)
    offset_keys = {
        "launcher_offset",
        "workspace_offset",
        "datetime_offset",
        "media_offset",
        "status_offset",
        "tray_offset",
    }
    for key, default in DEFAULT_BAR_SETTINGS.items():
        if isinstance(default, list):
            raw = current.get(key, default)
            if isinstance(raw, list):
                merged[key] = [str(item).strip() for item in raw if str(item).strip()]
            else:
                merged[key] = list(default)
            continue
        if isinstance(default, str):
            merged[key] = str(current.get(key, default)).strip()
            continue
        if isinstance(default, bool):
            merged[key] = bool(current.get(key, default))
            continue
        try:
            merged[key] = int(current.get(key, default))
        except Exception:
            merged[key] = default
        if key in offset_keys:
            merged[key] = max(-8, min(8, int(merged[key])))
        elif key == "workspace_count":
            merged[key] = max(1, min(10, int(merged[key])))
        elif key == "status_icon_limit":
            merged[key] = max(4, min(48, int(merged[key])))
        elif key == "bar_height":
            merged[key] = max(32, min(72, int(merged[key])))
        else:
            merged[key] = max(0, min(32, int(merged[key])))
    monitor_mode = str(merged.get("monitor_mode", MONITOR_MODE_PRIMARY)).strip().lower()
    merged["monitor_mode"] = (
        monitor_mode
        if monitor_mode
        in {MONITOR_MODE_PRIMARY, MONITOR_MODE_FOLLOW_MOUSE, MONITOR_MODE_NAMED}
        else MONITOR_MODE_PRIMARY
    )
    orientation_mode = str(merged.get("orientation_mode", "horizontal_top")).strip().lower()
    merged["orientation_mode"] = (
        orientation_mode
        if orientation_mode in {"horizontal_top", "vertical_left", "vertical_right"}
        else "horizontal_top"
    )
    merged["monitor_name"] = str(merged.get("monitor_name", "")).strip()
    return merged


def load_region_settings() -> dict[str, object]:
    return load_region_settings_from_payload(load_runtime_settings())


def load_bar_settings() -> dict[str, object]:
    return load_bar_settings_from_payload(load_runtime_settings())


def load_autolock_settings_from_payload(settings: object) -> dict[str, object]:
    current = settings.get("autolock", {}) if isinstance(settings, dict) else {}
    current = current if isinstance(current, dict) else {}
    try:
        timeout_minutes = max(1, min(60, int(current.get("timeout_minutes", 2))))
    except Exception:
        timeout_minutes = 2
    return {
        "enabled": bool(current.get("enabled", True)),
        "timeout_minutes": timeout_minutes,
    }


def lock_screen_command() -> list[str]:
    lock_script = SCRIPTS_DIR / "lock"
    if lock_script.exists():
        return [str(lock_script)]
    return []


def mail_now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def mail_storage_config() -> dict[str, str]:
    default = {"db_path": str(MAIL_STATE_DIR / "mail.sqlite3")}
    try:
        payload = json.loads(MAIL_STORAGE_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid mail storage config")
    except Exception:
        payload = {}
    return {
        "db_path": str(payload.get("db_path", default["db_path"])).strip()
        or default["db_path"],
    }


def mail_db_path() -> Path:
    return Path(mail_storage_config()["db_path"]).expanduser()


def mail_settings_from_payload(settings: object) -> dict[str, bool]:
    current = settings.get("mail", {}) if isinstance(settings, dict) else {}
    current = current if isinstance(current, dict) else {}
    return {
        "notify_new_messages": bool(current.get("notify_new_messages", True)),
        "play_notification_sound": bool(current.get("play_notification_sound", False)),
        "hide_notification_content": bool(
            current.get("hide_notification_content", False)
        ),
    }


def mail_re_sub(pattern: str, replacement: str, value: str) -> str:
    return re.sub(pattern, replacement, value, flags=re.IGNORECASE)


def decode_mail_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        for encoding in ("utf-8", "latin-1"):
            try:
                return value.decode(encoding)
            except Exception:
                continue
        return value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        value = str(value)
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            for codec in (encoding, "utf-8", "latin-1"):
                if not codec:
                    continue
                try:
                    parts.append(chunk.decode(codec))
                    break
                except Exception:
                    continue
            else:
                parts.append(chunk.decode("utf-8", errors="ignore"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def mail_html_to_text(value: str) -> str:
    text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("</p>", "\n\n").replace("</div>", "\n")
    text = text.replace("&nbsp;", " ")
    text = mail_re_sub(r"<style[\s\S]*?</style>", "", text)
    text = mail_re_sub(r"<script[\s\S]*?</script>", "", text)
    text = mail_re_sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = mail_re_sub(r"\r\n?", "\n", text)
    text = mail_re_sub(r"[ \t]+", " ", text)
    text = mail_re_sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def mail_message_parts(msg: Message) -> tuple[str, str]:
    html_body = ""
    text_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")
            content_type = (part.get_content_type() or "").lower()
            if content_type == "text/html" and not html_body:
                html_body = decoded
            elif content_type == "text/plain" and not text_body:
                text_body = decoded
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="ignore")
        except Exception:
            decoded = payload.decode("utf-8", errors="ignore")
        if (msg.get_content_type() or "").lower() == "text/html":
            html_body = decoded
        else:
            text_body = decoded
    if not text_body and html_body:
        text_body = mail_html_to_text(html_body)
    return html_body.strip(), text_body.strip()


def mail_snippet(text_body: str, html_body: str, limit: int = 180) -> str:
    source = text_body or mail_html_to_text(html_body)
    source = " ".join(source.split())
    if len(source) <= limit:
        return source
    return source[: limit - 1].rstrip() + "..."


def parse_mail_date(value: str) -> str:
    raw = decode_mail_text(value)
    if not raw:
        return mail_now_iso()
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.isoformat()
        return parsed.astimezone().isoformat()
    except Exception:
        return mail_now_iso()


MAIL_FETCH_UID_PATTERN = re.compile(r"\bUID\s+(\d+)\b", re.IGNORECASE)


def extract_uid_from_fetch_header(header_blob: str) -> str:
    if not header_blob:
        return ""
    match = MAIL_FETCH_UID_PATTERN.search(header_blob)
    if match:
        return match.group(1)
    for token in header_blob.split():
        if token.isdigit():
            return token
    return ""


def build_mail_message_key(account_id: int, folder: str, uid: str) -> str:
    return f"{account_id}|{quote(folder, safe='')}|{uid}"


def preferred_mail_sound_path() -> Path | None:
    for candidate in (
        Path("/usr/share/sounds/freedesktop/stereo/message-new-email.oga"),
        Path("/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"),
        Path("/usr/share/sounds/freedesktop/stereo/message.oga"),
        Path("/usr/share/sounds/freedesktop/stereo/complete.oga"),
        Path("/usr/share/sounds/freedesktop/stereo/complete.ogg"),
    ):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def truncate_mail_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


class WorkspaceDot(QPushButton):
    def __init__(self, num: int, callback):
        super().__init__("")
        self.num = num
        self.callback = callback
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(14, 14)
        self.setToolTip(f"WorkspaceDot {num}")
        self.clicked.connect(lambda: self.callback(self.num))
        self.state = "empty"
        self._hovered = False
        self.colors = {
            "focused": "#d0bcff",
            "occupied": "rgba(255,255,255,0.34)",
            "urgent": "#efb8c8",
            "empty": "rgba(255,255,255,0.14)",
        }
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; }"
        )

    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = dict(colors)
        self.update()

    def set_state(self, state: str) -> None:
        self.state = state
        self.update()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        dot_size = 14 if self.state == "focused" else 10
        inset = (self.width() - dot_size) / 2.0
        rect = QRectF(inset + 0.5, inset + 0.5, dot_size - 1.0, dot_size - 1.0)
        fill = (
            QColor("#e8def8")
            if self._hovered
            else QColor(self.colors.get(self.state, self.colors["empty"]))
        )
        border = QColor(255, 255, 255, 46)

        pen = painter.pen()
        pen.setWidthF(1.0)
        pen.setColor(border)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawEllipse(rect)


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ClickableFrame(QFrame):
    clicked = pyqtSignal()
    hoveredChanged = pyqtSignal(bool)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.hoveredChanged.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.hoveredChanged.emit(False)
        super().leaveEvent(event)


class EqualizerBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("equalizerBar")
        self.setFixedWidth(4)
        self.setFixedHeight(16)
        self.color = "#d0bcff"
        self._level = 0.08
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_color(self, color: str) -> None:
        if color == self.color:
            return
        self.color = color
        self.update()

    def set_level(self, level: float) -> None:
        normalized = max(0.0, min(1.0, float(level)))
        if abs(normalized - self._level) < 0.01:
            return
        self._level = normalized
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        bar_height = 4 + int(self._level * 12)
        rect = self.rect().adjusted(0, self.height() - bar_height, 0, 0)
        painter.drawRoundedRect(rect, 2.0, 2.0)


@pyqtClassInfo("D-Bus Interface", "org.kde.StatusNotifierWatcher")
class StatusNotifierWatcher(QObject):
    statusNotifierItemRegistered = pyqtSignal(str, name="StatusNotifierItemRegistered")
    statusNotifierItemUnregistered = pyqtSignal(
        str, name="StatusNotifierItemUnregistered"
    )
    statusNotifierHostRegistered = pyqtSignal(name="StatusNotifierHostRegistered")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[str] = []
        self._hosts: list[str] = []

    @pyqtSlot(str)
    def RegisterStatusNotifierItem(self, service_or_path: str) -> None:
        item_id = service_or_path.strip()
        if not item_id:
            return
        if item_id not in self._items:
            self._items.append(item_id)
            self.statusNotifierItemRegistered.emit(item_id)

    @pyqtSlot(str)
    def RegisterStatusNotifierHost(self, service: str) -> None:
        host = service.strip()
        if host and host not in self._hosts:
            self._hosts.append(host)
        self.statusNotifierHostRegistered.emit()

    @pyqtProperty("QStringList")
    def RegisteredStatusNotifierItems(self) -> list[str]:
        return list(self._items)

    @pyqtProperty(bool)
    def IsStatusNotifierHostRegistered(self) -> bool:
        return bool(self._hosts)

    @pyqtProperty(int)
    def ProtocolVersion(self) -> int:
        return 0

    def unregister_item(self, item_id: str) -> None:
        if item_id in self._items:
            self._items.remove(item_id)
            self.statusNotifierItemUnregistered.emit(item_id)


class StatusNotifierItemButton(QPushButton):
    def __init__(
        self,
        item_id: str,
        bus: QDBusConnection,
        parent: QWidget | None = None,
        icon_tint_getter: Callable[[], QColor | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.bus = bus
        self._icon_tint_getter = icon_tint_getter
        self._last_title = ""
        self.service, self.path = self._parse_item_id(item_id)
        self.iface = QDBusInterface(
            self.service, self.path, "org.kde.StatusNotifierItem", self.bus
        )
        self.setObjectName("trayButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setIconSize(QSize(16, 16))
        self.setFixedSize(22, 22)
        self.refresh()
        for signal_name in ("NewIcon", "NewTitle", "NewToolTip", "NewStatus"):
            self.bus.connect(
                self.service,
                self.path,
                "org.kde.StatusNotifierItem",
                signal_name,
                self.refresh,
            )

    @staticmethod
    def _parse_item_id(item_id: str) -> tuple[str, str]:
        if "/" in item_id:
            service, path = item_id.split("/", 1)
            return service, f"/{path}"
        return item_id, "/StatusNotifierItem"

    def _dbus_property(self, name: str, default=None):
        reply = QDBusInterface(
            self.service,
            self.path,
            "org.freedesktop.DBus.Properties",
            self.bus,
        ).call("Get", "org.kde.StatusNotifierItem", name)
        if not reply.arguments():
            return default
        value = reply.arguments()[0]
        return default if value is None else value

    def _icon_from_pixmaps(self, pixmaps) -> QIcon:
        if not isinstance(pixmaps, list) or not pixmaps:
            return QIcon()
        best = max(
            (
                entry
                for entry in pixmaps
                if isinstance(entry, tuple)
                and len(entry) == 3
                and entry[0] > 0
                and entry[1] > 0
            ),
            key=lambda entry: entry[0] * entry[1],
            default=None,
        )
        if best is None:
            return QIcon()
        width, height, data = best
        image = QImage(
            bytes(data), int(width), int(height), QImage.Format.Format_ARGB32
        )
        if image.isNull():
            return QIcon()
        return QIcon(QPixmap.fromImage(image.copy()))

    def _tint_icon(self, icon: QIcon) -> QIcon:
        if icon.isNull() or self._icon_tint_getter is None:
            return icon

        color = self._icon_tint_getter()
        if color is None:
            return icon

        pixmap = icon.pixmap(self.iconSize())
        if pixmap.isNull():
            return icon

        return QIcon(_tint_pixmap_from_alpha(pixmap, color))

    def _event_position(self, event) -> tuple[int, int]:
        point = event.globalPosition().toPoint()
        return point.x(), point.y()

    def _call_item_action(self, method: str, x: int, y: int) -> bool:
        if not self.iface.isValid():
            return False
        try:
            reply = self.iface.call(method, x, y)
        except Exception:
            return False
        return reply.type() != QDBusMessage.MessageType.ErrorMessage

    def _looks_like_zulucrypt(self) -> bool:
        haystack = (
            " ".join(
                [
                    str(self.item_id or ""),
                    str(self.service or ""),
                    str(self._last_title or ""),
                    str(self.toolTip() or ""),
                ]
            )
            .strip()
            .lower()
        )
        return "zulucrypt" in haystack or "zulu" in haystack

    def _x11_right_click_fallback(self) -> bool:
        if shutil.which("xdotool") is None:
            return False
        window_id = self._dbus_property("WindowId", 0)
        try:
            win = int(window_id or 0)
        except Exception:
            return False
        if win <= 0:
            return False
        # Try a context-menu key first (non-intrusive), then a direct RMB click.
        try:
            key_result = subprocess.run(
                ["xdotool", "key", "--window", str(win), "Menu"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if key_result.returncode == 0:
                return True
            click_result = subprocess.run(
                ["xdotool", "mousemove", "--window", str(win), "6", "6", "click", "3"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return click_result.returncode == 0
        except Exception:
            return False

    def _dispatch_right_click(self, x: int, y: int) -> None:
        handled = self._call_item_action("ContextMenu", x, y)
        if not handled:
            # Compatibility fallback for some legacy/bridged tray apps.
            handled = self._call_item_action("ContextMenu", 0, 0)
        if not handled:
            handled = self._call_item_action("SecondaryActivate", x, y)
        if not handled:
            handled = self._call_item_action("Activate", x, y)
        if not handled and self._looks_like_zulucrypt():
            self._x11_right_click_fallback()

    @pyqtSlot()
    def refresh(self) -> None:
        tooltip = self._dbus_property("ToolTip", ("", [], "", ""))
        title = (
            self._dbus_property("Title", "")
            or (tooltip[2] if isinstance(tooltip, tuple) and len(tooltip) > 2 else "")
            or self._dbus_property("Id", "")
            or self.service
        )
        icon_name = self._dbus_property("IconName", "") or (
            tooltip[0] if isinstance(tooltip, tuple) and len(tooltip) > 0 else ""
        )
        status = str(self._dbus_property("Status", "Active") or "Active")
        self._last_title = str(title)
        self.setToolTip(str(title))
        icon = QIcon.fromTheme(str(icon_name))
        if icon.isNull():
            icon = self._icon_from_pixmaps(self._dbus_property("IconPixmap", []))
        icon = self._tint_icon(icon)
        if not icon.isNull():
            self.setIcon(icon)
            self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText(str(title)[:1].upper())
        self.setVisible(status != "Passive")

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        x, y = self._event_position(event)
        if event.button() == Qt.MouseButton.RightButton:
            self._dispatch_right_click(x, y)
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            handled = self._call_item_action("SecondaryActivate", x, y)
            if not handled:
                self._call_item_action("Activate", x, y)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._call_item_action("Activate", x, y)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class StatusNotifierTray(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("trayHost")
        self.bus = QDBusConnection.sessionBus()
        self.watcher_service = "org.kde.StatusNotifierWatcher"
        self.host_service = f"org.kde.StatusNotifierHost-{os.getpid()}-1"
        self._watcher_process: subprocess.Popen[str] | None = None
        self._watcher_signals_connected = False
        self._icon_tint: QColor | None = None
        self.buttons: dict[str, StatusNotifierItemButton] = {}
        self.proxy: QDBusInterface | None = None

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setVisible(False)

        self._ensure_watcher()
        self.bus.connect(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameOwnerChanged",
            self._handle_name_owner_changed,
        )
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_items)
        self.refresh_timer.start(5000)
        QTimer.singleShot(0, self.refresh_items)

    def _ensure_watcher(self) -> None:
        self.proxy = QDBusInterface(
            self.watcher_service,
            "/StatusNotifierWatcher",
            self.watcher_service,
            self.bus,
        )
        if self.proxy.isValid():
            if not self._watcher_signals_connected:
                self.bus.connect(
                    self.watcher_service,
                    "/StatusNotifierWatcher",
                    self.watcher_service,
                    "StatusNotifierItemRegistered",
                    self._register_item,
                )
                self.bus.connect(
                    self.watcher_service,
                    "/StatusNotifierWatcher",
                    self.watcher_service,
                    "StatusNotifierItemUnregistered",
                    self._unregister_item,
                )
                self._watcher_signals_connected = True
        else:
            self.proxy = None
            self._watcher_signals_connected = False
            self._start_watcher_helper()

        if not self.bus.registerService(self.host_service):
            return
        if self.proxy is not None and self.proxy.isValid():
            self.proxy.call("RegisterStatusNotifierHost", self.host_service)

    def refresh_items(self) -> None:
        if self.proxy is None or not self.proxy.isValid():
            self._ensure_watcher()
        if self.proxy is None or not self.proxy.isValid():
            self._sync_visibility()
            return
        items = self._watcher_property("RegisteredStatusNotifierItems", [])
        if isinstance(items, list):
            for item_id in items:
                self._register_item(str(item_id))
        self._sync_visibility()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.bus.unregisterService(self.host_service)
        if self._watcher_process is not None and self._watcher_process.poll() is None:
            self._watcher_process.terminate()
        super().closeEvent(event)

    @pyqtSlot(str)
    def _register_item(self, item_id: str) -> None:
        service, _path = StatusNotifierItemButton._parse_item_id(item_id)
        bus_interface = self.bus.interface()
        if bus_interface is not None:
            reply = bus_interface.isServiceRegistered(service)
            if reply.isValid() and not bool(reply.value()):
                self._unregister_item(item_id)
                return
        if item_id in self.buttons:
            self.buttons[item_id].refresh()
            self._sync_visibility()
            return
        button = StatusNotifierItemButton(item_id, self.bus, self, self.icon_tint)
        self.buttons[item_id] = button
        self.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self._sync_visibility()

    @pyqtSlot(str)
    def _unregister_item(self, item_id: str) -> None:
        button = self.buttons.pop(item_id, None)
        if button is not None:
            self.layout.removeWidget(button)
            button.deleteLater()
        self._sync_visibility()

    @pyqtSlot(str, str, str)
    def _handle_name_owner_changed(
        self, name: str, _old_owner: str, new_owner: str
    ) -> None:
        if not name.startswith("org.") and not name.startswith(":"):
            return
        if not new_owner:
            to_remove = [
                item_id
                for item_id, button in self.buttons.items()
                if button.service == name
            ]
            for item_id in to_remove:
                self._unregister_item(item_id)

    def _sync_visibility(self) -> None:
        visible_buttons = 0
        for button in self.buttons.values():
            button.refresh()
            if not button.isHidden():
                visible_buttons += 1
        self.setVisible(visible_buttons > 0)

    def _start_watcher_helper(self) -> None:
        if self._watcher_process is not None and self._watcher_process.poll() is None:
            return
        if not STATUS_NOTIFIER_WATCHER.exists():
            return
        try:
            self._watcher_process = subprocess.Popen(
                [python_executable(), str(STATUS_NOTIFIER_WATCHER)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            QTimer.singleShot(250, self.refresh_items)
        except Exception:
            self._watcher_process = None

    def _watcher_property(self, name: str, default=None):
        reply = QDBusInterface(
            self.watcher_service,
            "/StatusNotifierWatcher",
            "org.freedesktop.DBus.Properties",
            self.bus,
        ).call("Get", self.watcher_service, name)
        if not reply.arguments():
            return default
        value = reply.arguments()[0]
        return default if value is None else value

    def icon_tint(self) -> QColor | None:
        return QColor(self._icon_tint) if self._icon_tint is not None else None

    def set_icon_tint(self, color: QColor | None) -> None:
        self._icon_tint = QColor(color) if color is not None else None
        for button in self.buttons.values():
            button.refresh()


class WeatherWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        city = configured_city()
        if city is None:
            self.loaded.emit(None)
            return
        self.loaded.emit(fetch_forecast(city))


class CapAlertWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        location = configured_alert_location()
        if location is None and not test_mode_enabled():
            self.loaded.emit([])
            return
        self.loaded.emit(fetch_active_alerts(location))


class WorkspaceStateWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        payload: dict[str, object] = {
            "focused_num": 1,
            "occupied": [],
            "urgent": [],
            "has_real_windows": False,
        }
        raw = run_cmd(["i3-msg", "-t", "get_workspaces"])
        if not raw:
            self.loaded.emit(payload)
            return
        try:
            workspaces = json.loads(raw)
        except Exception:
            self.loaded.emit(payload)
            return
        if not isinstance(workspaces, list):
            self.loaded.emit(payload)
            return
        occupied: set[int] = set()
        urgent: set[int] = set()
        focused_num = 1
        for ws in workspaces:
            if not isinstance(ws, dict):
                continue
            num = int(ws.get("num", 0) or 0)
            if num > 0:
                occupied.add(num)
            if ws.get("focused"):
                focused_num = num
            if ws.get("urgent"):
                urgent.add(num)
        payload["focused_num"] = focused_num
        payload["occupied"] = sorted(occupied)
        payload["urgent"] = sorted(urgent)
        try:
            payload["has_real_windows"] = focused_workspace_has_real_windows()
        except Exception:
            payload["has_real_windows"] = False
        self.loaded.emit(payload)


class MediaStateWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        summary = run_script("mpris.sh", "summary")
        title = "Play Something"
        artist = "Artist"
        status = "Stopped"
        if summary:
            parts = summary.split("\x1f")
            if len(parts) > 0 and parts[0]:
                title = parts[0]
            if len(parts) > 1 and parts[1]:
                artist = parts[1]
            if len(parts) > 2 and parts[2]:
                status = parts[2]
        self.loaded.emit(
            {
                "title": title,
                "artist": artist,
                "status": status,
            }
        )


class CavaWorker(QThread):
    frame_ready = pyqtSignal(object)
    stream_ended = pyqtSignal()

    def __init__(
        self, config_path: Path, bars: int, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._config_path = config_path
        self._bars = max(1, bars)
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._running = True

    def stop(self) -> None:
        self._running = False
        process = self._process
        if process is None:
            return
        try:
            process.terminate()
        except Exception:
            pass
        try:
            process.kill()
        except Exception:
            pass

    def run(self) -> None:
        try:
            self._process = subprocess.Popen(
                ["/usr/bin/cava", "-p", str(self._config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except Exception:
            self._process = None
            if self._running:
                self.stream_ended.emit()
            return

        process = self._process
        stdout = process.stdout
        if stdout is None:
            if self._running:
                self.stream_ended.emit()
            return

        try:
            while self._running:
                frame = stdout.readline()
                if not frame:
                    break
                parts = [part for part in frame.strip().split(";") if part != ""]
                if parts:
                    self.frame_ready.emit(parts[: self._bars])
        except Exception:
            pass
        finally:
            try:
                process.terminate()
            except Exception:
                pass
            try:
                process.wait(timeout=0.2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            self._process = None

        if self._running:
            self.stream_ended.emit()


class SystemStateWorker(QThread):
    loaded = pyqtSignal(object)

    def __init__(
        self, battery_base: Optional[Path], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._battery_base = battery_base

    def run(self) -> None:
        payload: dict[str, object] = {
            "connected": run_script("network.sh", "status") == "Connected",
            "wg_active": False,
            "selected_iface": "",
            "caffeine_on": run_script("caffeine.sh", "status") == "on",
            "caps_on": run_script("lockstatus.sh", "--caps-status") == "on",
            "num_on": run_script("lockstatus.sh", "--num-status") == "on",
            "battery_present": False,
            "battery_capacity": 0,
            "battery_status": "",
        }
        raw = run_script("vpn.sh", "--status")
        if raw:
            try:
                vpn_payload = json.loads(raw)
            except Exception:
                vpn_payload = {}
            if isinstance(vpn_payload, dict):
                payload["wg_active"] = vpn_payload.get("wireguard") == "on"
                payload["selected_iface"] = str(
                    vpn_payload.get("wg_selected", "")
                ).strip()

        if self._battery_base is not None:
            try:
                with open(
                    self._battery_base / "capacity", "r", encoding="utf-8"
                ) as handle:
                    payload["battery_capacity"] = int(handle.read().strip())
                with open(
                    self._battery_base / "status", "r", encoding="utf-8"
                ) as handle:
                    payload["battery_status"] = handle.read().strip()
                payload["battery_present"] = True
            except Exception:
                payload["battery_present"] = False
        self.loaded.emit(payload)


class UpdateCountWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        try:
            payload = collect_update_payload()
        except Exception:
            payload = {}
        self.loaded.emit(payload)


class HealthSnapshotWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        try:
            payload = load_current_snapshot(sync_remote=True)
        except Exception:
            payload = {}
        self.loaded.emit(payload)


class MailPollWorker(QThread):
    loaded = pyqtSignal(object)

    def __init__(
        self,
        due_account_ids: set[int],
        mail_settings: dict[str, bool],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._due_account_ids = {int(item) for item in due_account_ids if int(item) > 0}
        self._mail_settings = dict(mail_settings)

    def run(self) -> None:
        payload = {
            "available": False,
            "total_unread": 0,
            "accounts": [],
            "notifications": [],
            "synced_account_ids": [],
        }
        db_path = mail_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            self._ensure_schema(conn)
            accounts = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM accounts ORDER BY lower(label), lower(email_address)"
                ).fetchall()
            ]
            payload["available"] = bool(accounts)
            if not accounts:
                self.loaded.emit(payload)
                return
            notifications: list[dict[str, str | int]] = []
            synced_account_ids: list[int] = []
            logger.debug(
                "MailPollWorker scanning %d accounts (%d due)",
                len(accounts),
                len(self._due_account_ids),
            )
            for account in accounts:
                account_id = int(account.get("id", 0) or 0)
                if account_id <= 0 or account_id not in self._due_account_ids:
                    continue
                try:
                    folder_state = json.loads(
                        str(account.get("folder_state_json", "{}")) or "{}"
                    )
                except Exception:
                    folder_state = {}
                if not isinstance(folder_state, dict):
                    folder_state = {}
                inbox_name = "INBOX"
                account_label = (
                    str(account.get("label", "")).strip()
                    or str(account.get("email_address", "")).strip()
                    or f"id-{account_id}"
                )
                account_notifications = self._sync_account(
                    conn, account, inbox_name, folder_state
                )
                notifications.extend(account_notifications)
                if account_notifications:
                    logger.info(
                        "Account %s produced %d notification(s)",
                        account_label,
                        len(account_notifications),
                    )
                conn.execute(
                    "UPDATE accounts SET folders_json = ?, folder_state_json = ?, updated_at = ? WHERE id = ?",
                    (
                        json.dumps([inbox_name]),
                        json.dumps(folder_state),
                        mail_now_iso(),
                        account_id,
                    ),
                )
                conn.commit()
                synced_account_ids.append(account_id)

            account_rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT id, label, display_name, email_address FROM accounts ORDER BY lower(label), lower(email_address)"
                ).fetchall()
            ]
            counts = {
                int(row["account_id"]): int(row["unread_count"])
                for row in conn.execute(
                    "SELECT account_id, COUNT(*) AS unread_count FROM messages WHERE seen = 0 GROUP BY account_id"
                ).fetchall()
            }
            payload["accounts"] = [
                {
                    "id": int(account["id"]),
                    "label": str(account.get("label", "")).strip()
                    or str(account.get("email_address", "")).strip()
                    or "Mailbox",
                    "display_name": str(account.get("display_name", "")).strip(),
                    "email_address": str(account.get("email_address", "")).strip(),
                    "unread_count": counts.get(int(account["id"]), 0),
                }
                for account in account_rows
            ]
            payload["total_unread"] = sum(
                int(item["unread_count"]) for item in payload["accounts"]
            )
            payload["notifications"] = notifications
            payload["synced_account_ids"] = synced_account_ids
        except Exception:
            pass
        finally:
            conn.close()
        self.loaded.emit(payload)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                email_address TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                avatar_path TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                imap_host TEXT NOT NULL,
                imap_port INTEGER NOT NULL DEFAULT 993,
                imap_ssl INTEGER NOT NULL DEFAULT 1,
                smtp_host TEXT NOT NULL,
                smtp_port INTEGER NOT NULL DEFAULT 587,
                smtp_starttls INTEGER NOT NULL DEFAULT 1,
                smtp_ssl INTEGER NOT NULL DEFAULT 0,
                folders_json TEXT NOT NULL DEFAULT '[]',
                folder_state_json TEXT NOT NULL DEFAULT '{}',
                signature TEXT NOT NULL DEFAULT '',
                notify_enabled INTEGER NOT NULL DEFAULT 1,
                poll_interval_seconds INTEGER NOT NULL DEFAULT 90,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS messages (
                account_id INTEGER NOT NULL,
                folder TEXT NOT NULL,
                uid TEXT NOT NULL,
                message_id TEXT NOT NULL DEFAULT '',
                in_reply_to TEXT NOT NULL DEFAULT '',
                references_json TEXT NOT NULL DEFAULT '[]',
                subject TEXT NOT NULL DEFAULT '',
                from_name TEXT NOT NULL DEFAULT '',
                from_email TEXT NOT NULL DEFAULT '',
                to_line TEXT NOT NULL DEFAULT '',
                cc_line TEXT NOT NULL DEFAULT '',
                date_iso TEXT NOT NULL DEFAULT '',
                snippet TEXT NOT NULL DEFAULT '',
                body_html TEXT NOT NULL DEFAULT '',
                body_text TEXT NOT NULL DEFAULT '',
                raw_source BLOB,
                seen INTEGER NOT NULL DEFAULT 0,
                flagged INTEGER NOT NULL DEFAULT 0,
                has_attachments INTEGER NOT NULL DEFAULT 0,
                spam_score REAL NOT NULL DEFAULT 0.0,
                is_spam INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (account_id, folder, uid)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def _sync_account(
        self,
        conn: sqlite3.Connection,
        account: dict[str, object],
        folder: str,
        folder_state: dict[str, object],
    ) -> list[dict[str, str | int]]:
        host = str(account.get("imap_host", "")).strip()
        username = str(account.get("username", "")).strip()
        password = str(account.get("password", ""))
        if not host or not username or not password:
            return []
        account_id = int(account.get("id", 0) or 0)
        notifications: list[dict[str, str | int]] = []
        port = int(account.get("imap_port", 993) or 993)
        use_ssl = bool(account.get("imap_ssl", True))
        account_label = (
            str(account.get("display_name", "")).strip()
            or str(account.get("label", "")).strip()
            or str(account.get("email_address", "")).strip()
            or f"id-{account_id}"
        )
        client: imaplib.IMAP4 | None = None
        try:
            if use_ssl:
                client = imaplib.IMAP4_SSL(
                    host, port, ssl_context=ssl.create_default_context()
                )
            else:
                client = imaplib.IMAP4(host, port)
            client.login(username, password)
            status, _ = client.select(f'"{folder}"', readonly=True)
            if status != "OK":
                return []
            status, data = client.uid("search", None, "ALL")
            if status != "OK" or not data or not data[0]:
                return []
            uids = [item for item in decode_mail_text(data[0]).split() if item.strip()]
            if not uids:
                return []

            latest_uids = uids[-40:]
            fetched_messages: dict[str, dict[str, str]] = {}
            status, fetch_data = client.uid(
                "fetch", ",".join(latest_uids), "(RFC822 FLAGS)"
            )
            if status == "OK":
                for i in range(0, len(fetch_data or []), 2):
                    item = fetch_data[i]
                    if not item or not isinstance(item, tuple):
                        continue
                    header_blob = decode_mail_text(item[0])
                    raw_bytes = item[1]
                    uid = extract_uid_from_fetch_header(header_blob)
                    if not uid:
                        continue
                    flags_seen = "\\Seen" in header_blob
                    flags_flagged = "\\Flagged" in header_blob
                    msg = message_from_bytes(raw_bytes)
                    row_payload = self._store_message_record(
                        conn,
                        account_id,
                        folder,
                        uid,
                        msg,
                        raw_bytes,
                        flags_seen,
                        flags_flagged,
                        any(
                            "attachment"
                            in (part.get("Content-Disposition") or "").lower()
                            for part in msg.walk()
                        ),
                    )
                    if row_payload:
                        fetched_messages[uid] = row_payload
                conn.commit()

            latest_uid = uids[-1]
            last_uid = str(folder_state.get(folder, "")).strip()
            folder_state[folder] = latest_uid
            notify_enabled = bool(
                self._mail_settings.get("notify_new_messages", True)
            ) and bool(account.get("notify_enabled", True))
            if last_uid and notify_enabled:
                new_uids = [
                    uid for uid in uids if uid.isdigit() and int(uid) > int(last_uid)
                ][-3:]
                if new_uids:
                    logger.info(
                        "MailPollWorker detected %d new messages for account %s",
                        len(new_uids),
                        account.get("label") or account.get("email_address"),
                    )
                    for uid in new_uids:
                        if uid not in fetched_messages:
                            row_payload = self._fetch_and_store_single_message(
                                conn, client, account_id, folder, uid
                            )
                            if row_payload:
                                fetched_messages[uid] = row_payload
                for uid in new_uids:
                    row = fetched_messages.get(uid)
                    if not row:
                        row = self._fetch_and_store_single_message(
                            conn, client, account_id, folder, uid
                        )
                        if row:
                            fetched_messages[uid] = row
                    if not row:
                        logger.warning(
                            "MailPollWorker missing stored row for uid %s/%s (%s)",
                            uid,
                            folder,
                            account_label,
                        )
                        continue
                    notifications.append(
                        {
                            "account_id": account_id,
                            "folder": folder,
                            "message_key": build_mail_message_key(
                                account_id, folder, uid
                            ),
                            "account_label": str(
                                account.get("display_name", "")
                            ).strip()
                            or str(account.get("label", "")).strip()
                            or str(account.get("email_address", "")).strip()
                            or "Mailbox",
                            "subject": str(row["subject"] or "(No subject)"),
                            "snippet": str(row["snippet"] or ""),
                            "from_name": str(row["from_name"] or ""),
                            "from_email": str(row["from_email"] or ""),
                        }
                    )
        except Exception as exc:
            logger.exception(
                "MailPollWorker failed to sync account %s: %s", account_label, exc
            )
            return []
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
        return notifications

    def _store_message_record(
        self,
        conn: sqlite3.Connection,
        account_id: int,
        folder: str,
        uid: str,
        msg: Message,
        raw_bytes: bytes,
        flags_seen: bool,
        flags_flagged: bool,
        has_attachments: bool,
    ) -> dict[str, str] | None:
        from_name, from_email = parseaddr(decode_mail_text(msg.get("From", "")))
        body_html, body_text = mail_message_parts(msg)
        subject = decode_mail_text(msg.get("Subject", "")) or "(No subject)"
        snippet = mail_snippet(body_text, body_html)
        try:
            conn.execute(
                """
                INSERT INTO messages(
                    account_id, folder, uid, message_id, in_reply_to, references_json,
                    subject, from_name, from_email, to_line, cc_line, date_iso, snippet,
                    body_html, body_text, raw_source, seen, flagged, has_attachments, spam_score, is_spam
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, folder, uid) DO UPDATE SET
                    message_id=excluded.message_id,
                    in_reply_to=excluded.in_reply_to,
                    references_json=excluded.references_json,
                    subject=excluded.subject,
                    from_name=excluded.from_name,
                    from_email=excluded.from_email,
                    to_line=excluded.to_line,
                    cc_line=excluded.cc_line,
                    date_iso=excluded.date_iso,
                    snippet=excluded.snippet,
                    body_html=excluded.body_html,
                    body_text=excluded.body_text,
                    raw_source=excluded.raw_source,
                    seen=excluded.seen,
                    flagged=excluded.flagged,
                    has_attachments=excluded.has_attachments
                """,
                (
                    account_id,
                    folder,
                    uid,
                    decode_mail_text(msg.get("Message-ID", "")),
                    decode_mail_text(msg.get("In-Reply-To", "")),
                    json.dumps(
                        [
                            decode_mail_text(item)
                            for item in decode_mail_text(
                                msg.get("References", "")
                            ).split()
                            if item
                        ]
                    ),
                    subject,
                    from_name,
                    from_email,
                    decode_mail_text(msg.get("To", "")),
                    decode_mail_text(msg.get("Cc", "")),
                    parse_mail_date(decode_mail_text(msg.get("Date", ""))),
                    snippet,
                    body_html,
                    body_text,
                    raw_bytes,
                    1 if flags_seen else 0,
                    1 if flags_flagged else 0,
                    1 if has_attachments else 0,
                    0.0,
                    0,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to persist message %s/%s/%s", account_id, folder, uid
            )
            return None
        return {
            "subject": subject,
            "snippet": snippet,
            "from_name": from_name,
            "from_email": from_email,
        }

    def _fetch_and_store_single_message(
        self,
        conn: sqlite3.Connection,
        client: imaplib.IMAP4,
        account_id: int,
        folder: str,
        uid: str,
    ) -> dict[str, str] | None:
        try:
            status, fetch_data = client.uid("fetch", uid, "(RFC822 FLAGS)")
        except Exception as exc:
            logger.exception(
                "Single-message fetch failed for %s/%s/%s: %s",
                account_id,
                folder,
                uid,
                exc,
            )
            return None
        if status != "OK" or not fetch_data:
            logger.warning("IMAP fetch for uid %s/%s failed", uid, folder)
            return None
        for item in fetch_data:
            if not item or not isinstance(item, tuple):
                continue
            header_blob = decode_mail_text(item[0])
            raw_bytes = item[1]
            extracted_uid = extract_uid_from_fetch_header(header_blob)
            if extracted_uid != uid:
                continue
            flags_seen = "\\Seen" in header_blob
            flags_flagged = "\\Flagged" in header_blob
            msg = message_from_bytes(raw_bytes)
            return self._store_message_record(
                conn,
                account_id,
                folder,
                uid,
                msg,
                raw_bytes,
                flags_seen,
                flags_flagged,
                any(
                    "attachment" in (part.get("Content-Disposition") or "").lower()
                    for part in msg.walk()
                ),
            )
        return None


class CyberBar(QWidget):
    def __init__(self, ui_path: Optional[Path] = None):
        super().__init__()
        self.ui_path = ui_path
        self.loaded_fonts = load_app_fonts()
        self.theme = load_theme_palette()
        self._theme_use_matugen = bool(self.theme.use_matugen)
        self._theme_mtime = palette_mtime()
        self._settings_mtime = (
            SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        )
        self.runtime_settings = normalize_runtime_settings(load_runtime_settings())
        services = self.runtime_settings.get("services", {})
        self.service_settings = services if isinstance(services, dict) else {}
        self.bar_settings = load_bar_settings_from_payload(self.runtime_settings)
        self.region_settings = load_region_settings_from_payload(self.runtime_settings)
        self.autolock_settings = load_autolock_settings_from_payload(
            self.runtime_settings
        )
        self.ui_font = detect_font(
            theme_font_family("ui"),
            "Rubik",
            self.loaded_fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
        self._theme_font_signature = (
            theme_font_family("ui"),
            theme_font_family("display"),
            theme_font_family("mono"),
        )
        self._theme_refresh_restart_pending = False
        self.material_font = (
            self.loaded_fonts.get("material_icons")
            or self.loaded_fonts.get("material_icons_outlined")
            or self.loaded_fonts.get("material_symbols_outlined")
            or self.loaded_fonts.get("material_symbols_rounded")
            or detect_font(
                "Material Icons",
                "Material Icons Outlined",
                "Material Symbols Outlined",
                "Material Symbols Rounded",
            )
        )
        self.reminders_font = detect_font(
            "Symbols Nerd Font Mono",
            "Symbols Nerd Font",
            "JetBrainsMono Nerd Font Mono",
            "JetBrainsMono Nerd Font",
            "FiraCode Nerd Font Mono",
            "FiraCode Nerd Font",
            self.loaded_fonts.get("pomicons", ""),
            self.material_font,
        )
        self.workspace_buttons: dict[int, WorkspaceDot] = {}
        self._media_animation: Optional[QPropertyAnimation] = None
        self._media_playing = False
        self._media_visible = False
        self._cava_worker: Optional[CavaWorker] = None
        self._ai_popup_process: Optional[subprocess.Popen] = None
        self._launcher_process: Optional[subprocess.Popen] = None
        self._control_center_process: Optional[subprocess.Popen] = None
        self._wifi_popup_process: Optional[subprocess.Popen] = None
        self._vpn_popup_process: Optional[subprocess.Popen] = None
        self._christian_widget_process: Optional[subprocess.Popen] = None
        self._health_widget_process: Optional[subprocess.Popen] = None
        self._reminders_widget_process: Optional[subprocess.Popen] = None
        self._pomodoro_widget_process: Optional[subprocess.Popen] = None
        self._rss_widget_process: Optional[subprocess.Popen] = None
        self._obs_widget_process: Optional[subprocess.Popen] = None
        self._updates_widget_process: Optional[subprocess.Popen] = None
        self._crypto_widget_process: Optional[subprocess.Popen] = None
        self._vps_widget_process: Optional[subprocess.Popen] = None
        self._desktop_clock_process: Optional[subprocess.Popen] = None
        self._ntfy_popup_process: Optional[subprocess.Popen] = None
        self._weather_popup_process: Optional[subprocess.Popen] = None
        self._calendar_popup_process: Optional[subprocess.Popen] = None
        self._game_mode_popup_process: Optional[subprocess.Popen] = None
        self._powermenu_process: Optional[subprocess.Popen] = None
        self._cap_alerts_popup_process: Optional[subprocess.Popen] = None
        self._cap_alert_overlay_process: Optional[subprocess.Popen] = None
        self._weather_worker: Optional[WeatherWorker] = None
        self._cap_alert_worker: Optional[CapAlertWorker] = None
        self._updates_worker: Optional[UpdateCountWorker] = None
        self._health_worker: Optional[HealthSnapshotWorker] = None
        self._mail_worker: Optional[MailPollWorker] = None
        self._workspace_worker: Optional[WorkspaceStateWorker] = None
        self._media_worker: Optional[MediaStateWorker] = None
        self._system_state_worker: Optional[SystemStateWorker] = None
        self._weather_forecast: Optional[WeatherForecast] = None
        self._weather_alert_seen_keys: set[str] = set()
        self._cap_alerts: list[CapAlert] = []
        self._cap_alert_accent = "#FBC02D"
        self._pending_updates_total = 0
        self._health_snapshot: dict[str, object] = {}
        self._focused_workspace_has_real_windows = False
        self._cap_alert_seen_ids: set[str] = set()
        self._cap_alert_pulse_phase = 0.0
        self._cap_alert_pulse_tick = 0
        self._closing = False
        self._battery_base: Optional[Path] = self._detect_battery_base()
        self._settings_watcher: Optional[QFileSystemWatcher] = None
        self._settings_reload_timer: Optional[QTimer] = None
        self._control_center_launch_pending = False
        self._bar_icon_overrides = load_bar_icon_overrides()
        self._caps_lock_on: Optional[bool] = None
        self._num_lock_on: Optional[bool] = None
        self._autolock_armed = True
        self._autolock_launch_pending = False
        self._rss_last_interval_ms = 0
        self._mail_last_sync_at: dict[int, float] = {}
        self._mail_account_summary: list[dict[str, object]] = []
        self._mail_unread_total = 0
        self._mail_notification_interface: QDBusInterface | None = None
        self._mail_notification_actions: dict[int, list[str]] = {}
        self._setup_mail_notification_bus()
        self._obs_streaming = False
        self._obs_recording = False
        self._obs_flash_visible = True
        self._crypto_last_interval_ms = 0
        self._bar_plugin_hooks: dict[str, list[Callable[[], None]]] = {
            "settings_reloaded": [],
            "poll": [],
            "icons": [],
            "close": [],
        }
        self._loaded_bar_plugin_paths: set[str] = set()
        self._loaded_bar_plugin_ids: set[str] = set()
        self._bar_plugin_buttons: dict[str, QPushButton] = {}
        self._status_manual_overflow: set[str] = set()
        self._status_managed_widgets: list[QWidget] = []
        self._status_overflow_popup: QFrame | None = None
        self._status_overflow_layout: QVBoxLayout | None = None
        self._status_overflow_button: QPushButton | None = None
        self._status_overflow_open = False
        self._setup_window()
        self._build_ui()
        self._load_bar_plugins()
        self._apply_bar_icon_overrides()
        self._apply_styles()
        apply_antialias_font(self)
        self._setup_settings_watcher()
        self._start_polls()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeDock, True)
        self.setWindowTitle("CyberBar")

        self._position_on_target_screen(int(self.bar_settings.get("bar_height", 40)))

    def _target_screen(self) -> QScreen | None:
        monitor_mode = (
            str(self.bar_settings.get("monitor_mode", MONITOR_MODE_PRIMARY))
            .strip()
            .lower()
        )
        monitor_name = str(self.bar_settings.get("monitor_name", "")).strip()
        return preferred_bar_screen(monitor_mode, monitor_name)

    def _bar_orientation_mode(self) -> str:
        value = str(self.bar_settings.get("orientation_mode", "horizontal_top")).strip().lower()
        if value in {"vertical_left", "vertical_right"}:
            return value
        return "horizontal_top"

    def _position_on_target_screen(self, bar_height: int | None = None) -> None:
        screen = self._target_screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        target_height = bar_height if bar_height is not None else self.height()
        orientation = self._bar_orientation_mode()
        if orientation == "horizontal_top":
            self.setFixedSize(geo.width(), max(1, int(target_height)))
            self.move(geo.x(), geo.y())
            return
        sidebar_width = max(220, min(460, int(target_height) * 8))
        self.setFixedSize(sidebar_width, max(1, geo.height()))
        if orientation == "vertical_right":
            x = geo.x() + geo.width() - sidebar_width
        else:
            x = geo.x()
        self.move(x, geo.y())

    def _build_ui(self) -> None:
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(12, 4, 12, 4)
        self.outer_layout.setSpacing(0)

        self.bar_surface = QFrame()
        self.bar_surface.setObjectName("barSurface")
        self.outer_layout.addWidget(self.bar_surface)

        self.root_layout = QHBoxLayout(self.bar_surface)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(14)

        left_wrap = QWidget()
        self.left_wrap_widget = left_wrap
        self.left_layout = QHBoxLayout(left_wrap)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        self.launcher_chip = QFrame()
        self.launcher_chip.setObjectName("launcherChip")
        self.launcher_layout = QHBoxLayout(self.launcher_chip)
        self.launcher_layout.setContentsMargins(
            8, 4, 8, 4
        )  # top/bottom margins move the row vertically
        self.launcher_layout.setSpacing(6)  # spacing only changes the horizontal gap
        self.launcher_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.ai_button = self._icon_button("auto_awesome")
        self.ai_button.setObjectName("aiToggleButton")
        self.ai_button.setCheckable(True)
        self.ai_button.setFixedSize(28, 24)
        self.ai_button.pressed.connect(self._toggle_ai_popup)
        self.launcher_trigger = ClickableFrame()
        self.launcher_trigger.setObjectName("launcherTrigger")
        self.launcher_trigger.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.launcher_trigger.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.launcher_trigger.setFixedHeight(20)
        self.launcher_trigger.clicked.connect(self._open_launcher)
        self.launcher_trigger.hoveredChanged.connect(
            self._update_launcher_wordmark_colors
        )
        self.launcher_trigger_layout = QHBoxLayout(self.launcher_trigger)
        self.launcher_trigger_layout.setContentsMargins(10, 0, 10, 0)
        self.launcher_trigger_layout.setSpacing(5)
        self.launcher_trigger_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.launcher_note = QLabel("♪")
        self.launcher_note.setObjectName("launcherNote")
        self.launcher_note.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.launcher_note.setFixedSize(12, 16)
        self.launcher_text = QLabel("hanauta")
        self.launcher_text.setObjectName("launcherText")
        self.launcher_text.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.launcher_text.setFixedHeight(16)
        self.launcher_trigger_layout.addWidget(self.launcher_note)
        self.launcher_trigger_layout.addWidget(self.launcher_text)
        self.launcher_layout.addWidget(self.ai_button)
        self.launcher_layout.addWidget(self.launcher_trigger)
        self.launcher_layout.setAlignment(self.ai_button, Qt.AlignmentFlag.AlignVCenter)
        self.launcher_layout.setAlignment(
            self.launcher_trigger, Qt.AlignmentFlag.AlignVCenter
        )
        self.ai_wrap = self._wrap_movable(self.launcher_chip)
        self.left_layout.addWidget(self.ai_wrap)
        self.launcher_wrap = self.ai_wrap

        self.workspace_chip = QFrame()
        self.workspace_chip.setObjectName("workspaceChip")
        self.workspace_layout = QHBoxLayout(self.workspace_chip)
        self.workspace_layout.setContentsMargins(12, 4, 12, 4)
        self.workspace_layout.setSpacing(8)

        self.workspace_label = QLabel("Workspace 1")
        self.workspace_label.setObjectName("workspaceLabel")
        self.workspace_layout.addWidget(self.workspace_label)

        dots_wrap = QWidget()
        self.dots_layout = QHBoxLayout(dots_wrap)
        self.dots_layout.setContentsMargins(0, 0, 0, 0)
        self.dots_layout.setSpacing(6)
        self._rebuild_workspace_buttons()
        self.workspace_layout.addWidget(dots_wrap)
        self.workspace_wrap = self._wrap_movable(self.workspace_chip)
        self.left_layout.addWidget(self.workspace_wrap)
        self.root_layout.addWidget(left_wrap, 0, Qt.AlignmentFlag.AlignLeft)

        center_wrap = QWidget()
        self.center_wrap_widget = center_wrap
        self.center_layout = QHBoxLayout(center_wrap)
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(10)

        self.datetime_chip = QFrame()
        self.datetime_chip.setObjectName("dateTimeChip")
        self.datetime_layout = QHBoxLayout(self.datetime_chip)
        self.datetime_layout.setContentsMargins(12, 4, 12, 4)
        self.datetime_layout.setSpacing(8)

        self.weather_icon = AnimatedWeatherIcon(18)
        self.weather_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.weather_icon.clicked.connect(self._toggle_weather_popup)
        self.weather_icon.hide()
        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("timeLabel")
        self.date_label = ClickableLabel("--")
        self.date_label.setObjectName("dateLabel")
        self.date_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.date_label.clicked.connect(self._toggle_calendar_popup)
        self.health_pill = ClickableFrame()
        self.health_pill.setObjectName("healthPill")
        self.health_pill.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.health_pill.clicked.connect(self._open_health_widget)
        self.health_pill_layout = QHBoxLayout(self.health_pill)
        self.health_pill_layout.setContentsMargins(6, 2, 8, 2)
        self.health_pill_layout.setSpacing(4)
        self.health_pill_icon = QLabel(material_icon("favorite"))
        self.health_pill_icon.setObjectName("healthPillIcon")
        self.health_pill_icon.setFont(QFont(self.material_font, 14))
        self.health_pill_value = QLabel("--")
        self.health_pill_value.setObjectName("healthPillValue")
        self.health_pill_layout.addWidget(self.health_pill_icon)
        self.health_pill_layout.addWidget(self.health_pill_value)
        self.mail_wrap = ClickableFrame()
        self.mail_wrap.setObjectName("mailStatusWrap")
        self.mail_wrap.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mail_wrap.clicked.connect(self._open_mail_client)
        self.mail_layout = QHBoxLayout(self.mail_wrap)
        self.mail_layout.setContentsMargins(0, 0, 0, 0)
        self.mail_layout.setSpacing(4)
        self.mail_button = QPushButton(self._icon_text("mail"))
        self.mail_button.setObjectName("statusIconButton")
        self.mail_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mail_button.clicked.connect(self._open_mail_client)
        self.mail_count = QLabel("0")
        self.mail_count.setObjectName("mailUnreadCount")
        self.mail_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mail_layout.addWidget(self.mail_button)
        self.mail_layout.addWidget(self.mail_count)
        self.updates_pill = ClickableFrame()
        self.updates_pill.setObjectName("updatesPill")
        self.updates_pill.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.updates_pill.clicked.connect(self._check_updates)
        self.updates_pill_layout = QHBoxLayout(self.updates_pill)
        self.updates_pill_layout.setContentsMargins(6, 2, 8, 2)
        self.updates_pill_layout.setSpacing(4)
        self.updates_pill_icon = QLabel(material_icon("system_update"))
        self.updates_pill_icon.setObjectName("updatesPillIcon")
        self.updates_pill_icon.setFont(QFont(self.material_font, 14))
        self.updates_pill_count = QLabel("0")
        self.updates_pill_count.setObjectName("updatesPillCount")
        self.updates_pill_layout.addWidget(self.updates_pill_icon)
        self.updates_pill_layout.addWidget(self.updates_pill_count)
        self.locale_button = QPushButton(self._icon_text("public"))
        self.locale_button.setObjectName("regionButton")
        self.locale_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.locale_button.setFont(QFont(self.material_font, 18))
        self.locale_button.clicked.connect(self._open_region_settings)
        self.datetime_layout.addWidget(self.weather_icon)
        self.datetime_layout.addWidget(self.time_label)
        self.datetime_layout.addWidget(self.date_label)
        self.datetime_layout.addWidget(self.health_pill)
        self.datetime_layout.addWidget(self.mail_wrap)
        self.datetime_layout.addWidget(self.updates_pill)
        self.datetime_layout.addWidget(self.locale_button)
        self.btn_control_center = self._icon_button("dashboard")
        self.btn_control_center.setObjectName("utilityButton")
        self.btn_control_center.setCheckable(True)
        self.btn_control_center.pressed.connect(self._toggle_notifications)
        self.datetime_layout.addWidget(self.btn_control_center)
        self.datetime_wrap = self._wrap_movable(self.datetime_chip)
        self.center_layout.addWidget(self.datetime_wrap)

        self.media_chip = QFrame()
        self.media_chip.setObjectName("mediaChip")
        self.media_chip.setProperty("active", False)
        self.media_opacity = QGraphicsOpacityEffect(self.media_chip)
        self.media_chip.setGraphicsEffect(self.media_opacity)
        self.media_opacity.setOpacity(0.0)
        self.media_layout = QHBoxLayout(self.media_chip)
        self.media_layout.setContentsMargins(14, 4, 14, 4)
        self.media_layout.setSpacing(8)

        self.media_icon = QLabel(self._icon_text("music_note"))
        self.media_icon.setObjectName("mediaIcon")
        self.media_icon.setFont(QFont(self.material_font, 16))
        self.media_equalizer = QWidget()
        self.media_equalizer.setObjectName("equalizerWrap")
        self.equalizer_layout = QHBoxLayout(self.media_equalizer)
        self.equalizer_layout.setContentsMargins(0, 0, 0, 0)
        self.equalizer_layout.setSpacing(3)
        self.equalizer_bars: list[EqualizerBar] = []
        for _ in range(6):
            bar = EqualizerBar()
            self.equalizer_bars.append(bar)
            self.equalizer_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignBottom)
        self._equalizer_targets: list[float] = [0.08] * len(self.equalizer_bars)
        self._equalizer_levels: list[float] = [0.08] * len(self.equalizer_bars)
        self.media_text = QLabel("Nothing playing")
        self.media_text.setObjectName("mediaText")
        self.media_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.media_prev = self._icon_button("skip_previous")
        self.media_play = self._icon_button("play_arrow")
        self.media_next = self._icon_button("skip_next")
        self.media_prev.clicked.connect(lambda: run_script_bg("mpris.sh", "--previous"))
        self.media_play.clicked.connect(lambda: run_script_bg("mpris.sh", "--toggle"))
        self.media_next.clicked.connect(lambda: run_script_bg("mpris.sh", "--next"))
        for btn in (self.media_prev, self.media_play, self.media_next):
            btn.setObjectName("mediaControl")

        self.media_layout.addWidget(self.media_icon)
        self.media_layout.addWidget(self.media_equalizer)
        self.media_layout.addWidget(self.media_text)
        self.media_layout.addWidget(self.media_prev)
        self.media_layout.addWidget(self.media_play)
        self.media_layout.addWidget(self.media_next)
        self.media_wrap = self._wrap_movable(self.media_chip)
        self.center_layout.addWidget(self.media_wrap)
        self.root_layout.addWidget(center_wrap, 1, Qt.AlignmentFlag.AlignCenter)

        right_wrap = QWidget()
        self.right_wrap_widget = right_wrap
        self.right_layout = QHBoxLayout(right_wrap)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)

        self.cap_alert_chip = ClickableFrame()
        self.cap_alert_chip.setObjectName("capAlertChip")
        self.cap_alert_chip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cap_alert_chip.clicked.connect(self._open_cap_alerts_popup)
        self.cap_alert_layout = QHBoxLayout(self.cap_alert_chip)
        self.cap_alert_layout.setContentsMargins(10, 2, 12, 2)
        self.cap_alert_layout.setSpacing(8)
        self.cap_alert_warning = QLabel(material_icon("warning"))
        self.cap_alert_warning.setObjectName("capAlertWarning")
        self.cap_alert_warning.setFont(QFont(self.material_font, 16))
        self.cap_alert_warning_opacity = QGraphicsOpacityEffect(self.cap_alert_warning)
        self.cap_alert_warning_opacity.setOpacity(1.0)
        self.cap_alert_warning.setGraphicsEffect(self.cap_alert_warning_opacity)
        self.cap_alert_icon = AnimatedWeatherIcon(32)
        self.cap_alert_text = QLabel("Local weather alerts")
        self.cap_alert_text.setObjectName("capAlertText")
        self.cap_alert_text.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
        )
        self.cap_alert_text_shadow = QGraphicsDropShadowEffect(self.cap_alert_text)
        self.cap_alert_text_shadow.setBlurRadius(2.8)
        self.cap_alert_text_shadow.setOffset(0, 1.8)
        self.cap_alert_text_shadow.setColor(QColor(0, 0, 0, 220))
        self.cap_alert_text.setGraphicsEffect(self.cap_alert_text_shadow)
        self.cap_alert_layout.addWidget(self.cap_alert_warning)
        self.cap_alert_layout.addWidget(self.cap_alert_icon)
        self.cap_alert_layout.addWidget(self.cap_alert_text)
        self.cap_alert_chip.hide()
        self.cap_alert_glow_frame = QFrame(self.cap_alert_chip)
        self.cap_alert_glow_frame.setObjectName("capAlertGlow")
        self.cap_alert_glow_frame.lower()
        self.cap_alert_glow_frame.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.cap_alert_glow_frame.hide()

        self.status_chip = QFrame()
        self.status_chip.setObjectName("connectivityChip")
        self.status_layout = QHBoxLayout(self.status_chip)
        self.status_layout.setContentsMargins(10, 4, 10, 4)
        self.status_layout.setSpacing(8)

        self.net_icon = QPushButton(self._icon_text("wifi"))
        self.net_icon.setObjectName("statusIconButton")
        self.net_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.net_icon.setCheckable(True)
        self.net_icon.clicked.connect(self._toggle_wifi_popup)
        self.vpn_icon = QPushButton("")
        self.vpn_icon.setObjectName("statusIconButton")
        self.vpn_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.vpn_icon.setCheckable(True)
        self.vpn_icon.setText(self._icon_text("vpn_key"))
        self.vpn_icon.clicked.connect(self._toggle_vpn_popup)
        self.christian_button = QPushButton("")
        self.christian_button.setObjectName("statusIconButton")
        self.christian_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.christian_button.clicked.connect(self._open_christian_widget)
        self.christian_button.setIconSize(QSize(16, 16))
        self.reminders_button = QPushButton(REMINDERS_BAR_GLYPH)
        self.reminders_button.setObjectName("statusIconButton")
        self.reminders_button.setProperty("nerdIcon", True)
        self.reminders_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.reminders_button.clicked.connect(self._open_reminders_widget)
        self.caps_lock_button = QPushButton("A")
        self.caps_lock_button.setObjectName("statusLockButton")
        self.caps_lock_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.caps_lock_button.clicked.connect(lambda: self._toggle_lock_state("caps"))
        self.caps_lock_button.hide()
        self.num_lock_button = QPushButton("1")
        self.num_lock_button.setObjectName("statusLockButton")
        self.num_lock_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.num_lock_button.clicked.connect(lambda: self._toggle_lock_state("num"))
        self.num_lock_button.hide()
        self.pomodoro_button = QPushButton(self._icon_text("timer"))
        self.pomodoro_button.setObjectName("statusIconButton")
        self.pomodoro_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pomodoro_button.clicked.connect(self._open_pomodoro_widget)
        self.rss_button = QPushButton(self._icon_text("public"))
        self.rss_button.setObjectName("statusIconButton")
        self.rss_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rss_button.clicked.connect(self._open_rss_widget)
        self.obs_button = QPushButton(self._icon_text("videocam"))
        self.obs_button.setObjectName("statusIconButton")
        self.obs_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.obs_button.clicked.connect(self._open_obs_widget)
        self.crypto_button = QPushButton(self._icon_text("show_chart"))
        self.crypto_button.setObjectName("statusIconButton")
        self.crypto_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.crypto_button.clicked.connect(self._open_crypto_widget)
        self.ntfy_button = QPushButton(self._icon_text("notifications"))
        self.ntfy_button.setObjectName("statusIconButton")
        self.ntfy_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ntfy_button.setCheckable(True)
        self.ntfy_button.clicked.connect(self._toggle_ntfy_popup)
        self.game_mode_button = QPushButton(self._icon_text("sports_esports"))
        self.game_mode_button.setObjectName("statusIconButton")
        self.game_mode_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.game_mode_button.setCheckable(True)
        self.game_mode_button.clicked.connect(self._toggle_game_mode_popup)
        self.battery_icon = QLabel(self._icon_text("battery_full"))
        self.battery_icon.setObjectName("statusIcon")
        self.caffeine_icon = QLabel(self._icon_text("coffee"))
        self.caffeine_icon.setObjectName("statusIcon")
        self.battery_value = QLabel("100")
        self.battery_value.setObjectName("batteryValue")
        for label in (
            self.net_icon,
            self.vpn_icon,
            self.pomodoro_button,
            self.rss_button,
            self.obs_button,
            self.crypto_button,
            self.mail_button,
            self.ntfy_button,
            self.game_mode_button,
            self.battery_icon,
            self.caffeine_icon,
        ):
            label.setFont(QFont(self.material_font, 16))
        self.reminders_button.setFont(QFont(self.reminders_font, 16))
        self.caps_lock_button.setFont(QFont(self.ui_font, 10, QFont.Weight.Bold))
        self.num_lock_button.setFont(QFont(self.ui_font, 10, QFont.Weight.Bold))
        self.status_layout.addWidget(self.net_icon)
        self.status_layout.addWidget(self.vpn_icon)
        self.status_layout.addWidget(self.christian_button)
        self.status_layout.addWidget(self.reminders_button)
        self.status_layout.addWidget(self.caps_lock_button)
        self.status_layout.addWidget(self.num_lock_button)
        self.status_layout.addWidget(self.pomodoro_button)
        self.status_layout.addWidget(self.rss_button)
        self.status_layout.addWidget(self.obs_button)
        self.status_layout.addWidget(self.crypto_button)
        self.status_layout.addWidget(self.ntfy_button)
        self.status_layout.addWidget(self.game_mode_button)
        self.status_layout.addWidget(self.caffeine_icon)
        self.status_layout.addWidget(self.battery_icon)
        self.status_layout.addWidget(self.battery_value)
        self.btn_clip = self._icon_button("content_paste")
        self.btn_clip.setObjectName("statusIconButton")
        self.btn_clip.clicked.connect(self._open_clipboard)
        self.btn_power = self._icon_button("power_settings_new")
        self.btn_power.setObjectName("statusIconButton")
        self.btn_power.setCheckable(True)
        self.btn_power.clicked.connect(self._toggle_powermenu)

        self.tray_host = StatusNotifierTray(self)
        self.tray_host.setProperty("embedded", True)
        self.tray_host.setToolTip("Qt StatusNotifier tray")
        self.tray_wrap = self._wrap_movable(self.tray_host)
        self._status_overflow_button = QPushButton("↑↓")
        self._status_overflow_button.setObjectName("statusIconButton")
        self._status_overflow_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._status_overflow_button.setCheckable(True)
        self._status_overflow_button.setProperty("iconKey", "overflow_vertical")
        self._status_overflow_button.clicked.connect(self._toggle_status_overflow)
        self._status_overflow_button.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._status_overflow_button.customContextMenuRequested.connect(
            self._show_overflow_button_menu
        )
        self.status_layout.addWidget(self.btn_clip)
        self.status_layout.addWidget(self.tray_wrap, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_layout.addWidget(self._status_overflow_button)
        self.status_layout.addWidget(self.btn_power)
        self._create_status_overflow()
        self.status_wrap = self._wrap_movable(self.status_chip)
        self.right_layout.addWidget(self.cap_alert_chip)
        self.right_layout.addWidget(self.status_wrap)
        self.root_layout.addWidget(right_wrap, 0, Qt.AlignmentFlag.AlignRight)

        has_battery = self._battery_base is not None
        self.caffeine_icon.setVisible(False)
        self.battery_icon.setVisible(has_battery)
        self.battery_value.setVisible(has_battery)
        self._set_vpn_button_icon(False)
        self._set_christian_button_icon()
        self._sync_health_pill_visibility()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_mail_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._register_status_widget(self.net_icon, "net_icon")
        self._register_status_widget(self.vpn_icon, "vpn_icon")
        self._register_status_widget(self.christian_button, "christian_widget")
        self._register_status_widget(self.reminders_button, "reminders_widget")
        self._register_status_widget(self.caps_lock_button, "caps_lock")
        self._register_status_widget(self.num_lock_button, "num_lock")
        self._register_status_widget(self.pomodoro_button, "pomodoro_widget")
        self._register_status_widget(self.rss_button, "rss_widget")
        self._register_status_widget(self.obs_button, "obs_widget")
        self._register_status_widget(self.crypto_button, "crypto_widget")
        self._register_status_widget(self.ntfy_button, "ntfy")
        self._register_status_widget(self.game_mode_button, "game_mode")
        self._register_status_widget(self.caffeine_icon, "caffeine")
        self._register_status_widget(self.battery_icon, "battery_icon")
        self._register_status_widget(self.battery_value, "battery_value")
        self._register_status_widget(self.btn_clip, "clipboard")
        self._register_status_widget(self.tray_wrap, "tray_wrap")
        self._status_manual_overflow.add("tray_wrap")
        self._run_bar_plugin_hooks("settings_reloaded")
        self._sync_status_overflow()
        self._sync_cap_alert_chip()
        self._apply_bar_settings()
        self._apply_debug_tooltips_setting()

    def _icon_button(self, icon_name: str) -> QPushButton:
        button = QPushButton(self._icon_text(icon_name))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setProperty("iconKey", icon_name)
        return button

    def _icon_text(self, icon_name: str) -> str:
        return self._bar_icon_overrides.get(icon_name, material_icon(icon_name))

    def _register_bar_plugin_hook(
        self, kind: str, callback: Callable[[], None]
    ) -> None:
        hooks = self._bar_plugin_hooks.get(kind)
        if hooks is None or not callable(callback):
            return
        hooks.append(callback)

    def _run_bar_plugin_hooks(self, kind: str) -> None:
        hooks = self._bar_plugin_hooks.get(kind, [])
        for callback in list(hooks):
            try:
                callback()
            except Exception:
                continue

    def _add_status_plugin_button(
        self,
        key: str,
        glyph: str,
        *,
        tooltip: str = "",
        checkable: bool = False,
        on_click: Callable[[], None] | None = None,
        font_size: int = 16,
    ) -> QPushButton:
        existing = self._bar_plugin_buttons.get(key)
        if existing is not None:
            return existing
        button = QPushButton(glyph)
        button.setObjectName("statusIconButton")
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setCheckable(checkable)
        button.setFont(QFont(self.material_font, font_size))
        button.setProperty("statusKey", f"plugin:{key}")
        if tooltip:
            button.setToolTip(tooltip)
        if on_click is not None:
            button.clicked.connect(on_click)
        anchor_index = self.status_layout.indexOf(self.caffeine_icon)
        if anchor_index >= 0:
            self.status_layout.insertWidget(anchor_index, button)
        else:
            self.status_layout.addWidget(button)
        self._bar_plugin_buttons[key] = button
        self._register_status_widget(button, str(button.property("statusKey")))
        self._sync_status_overflow()
        return button

    def _register_status_widget(self, widget: QWidget, key: str) -> None:
        if widget is None:
            return
        resolved_key = str(key or "").strip() or f"widget:{id(widget)}"
        widget.setProperty("statusKey", resolved_key)
        if widget not in self._status_managed_widgets:
            self._status_managed_widgets.append(widget)
        if resolved_key == "tray_wrap":
            # Preserve tray item native right-click behavior (ContextMenu on each app).
            return
        if widget.property("statusMenuHooked") != True:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda point, current=widget: self._show_status_context_menu(
                    current, point
                )
            )
            widget.setProperty("statusMenuHooked", True)

    def _show_overflow_button_menu(self, point: QPoint) -> None:
        if self._status_overflow_button is None:
            return
        menu = QMenu(self)
        tray_in_overflow = "tray_wrap" in self._status_manual_overflow
        tray_action = QAction(
            "Move tray to bar" if tray_in_overflow else "Move tray to dropdown", menu
        )
        menu.addAction(tray_action)
        selected = menu.exec(self._status_overflow_button.mapToGlobal(point))
        if selected != tray_action:
            return
        if tray_in_overflow:
            self._status_manual_overflow.discard("tray_wrap")
        else:
            self._status_manual_overflow.add("tray_wrap")
        self._sync_status_overflow()

    def _show_status_context_menu(self, widget: QWidget, point: QPoint) -> None:
        key = str(widget.property("statusKey") or "").strip()
        if not key:
            return
        in_overflow = (
            self._status_overflow_layout is not None
            and self._status_overflow_layout.indexOf(widget) >= 0
        )
        menu = QMenu(self)
        move_action = QAction(
            "Move to bar" if in_overflow else "Move to overflow", menu
        )
        menu.addAction(move_action)
        selected = menu.exec(widget.mapToGlobal(point))
        if selected != move_action:
            return
        if in_overflow:
            self._status_manual_overflow.discard(key)
        else:
            self._status_manual_overflow.add(key)
        self._sync_status_overflow()

    def _create_status_overflow(self) -> None:
        if self._status_overflow_popup is not None:
            return
        popup = QFrame(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        popup.setObjectName("statusOverflowPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        shadow = QGraphicsDropShadowEffect(popup)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 160))
        popup.setGraphicsEffect(shadow)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self._status_overflow_popup = popup
        self._status_overflow_layout = layout

    def _toggle_status_overflow(self) -> None:
        if self._status_overflow_popup is None or self._status_overflow_button is None:
            return
        if (
            self._status_overflow_layout is None
            or self._status_overflow_layout.count() == 0
        ):
            return
        if self._status_overflow_open:
            self._status_overflow_popup.hide()
            self._status_overflow_open = False
        else:
            self._sync_status_overflow()
            self._status_overflow_popup.adjustSize()
            orientation = self._bar_orientation_mode()
            button_rect = self._status_overflow_button.rect()
            popup_size = self._status_overflow_popup.sizeHint()
            if orientation == "vertical_left":
                anchor = self._status_overflow_button.mapToGlobal(button_rect.topRight())
                x = anchor.x() + 8
                y = anchor.y()
            elif orientation == "vertical_right":
                anchor = self._status_overflow_button.mapToGlobal(button_rect.topLeft())
                x = anchor.x() - popup_size.width() - 8
                y = anchor.y()
            else:
                anchor = self._status_overflow_button.mapToGlobal(
                    self._status_overflow_button.rect().bottomLeft()
                )
                x = anchor.x()
                y = anchor.y() + 8
            self._status_overflow_popup.move(x, y)
            self._status_overflow_popup.show()
            self._status_overflow_open = True
        self._status_overflow_button.setChecked(self._status_overflow_open)
        if self._bar_orientation_mode() in {"vertical_left", "vertical_right"}:
            self._status_overflow_button.setText("↑↓")
        else:
            icon_name = "expand_more" if self._status_overflow_open else "expand_less"
            self._status_overflow_button.setText(self._icon_text(icon_name))

    def _sync_status_overflow(self) -> None:
        if self._status_overflow_layout is None or self._status_overflow_button is None:
            return
        vertical_mode = self._bar_orientation_mode() in {"vertical_left", "vertical_right"}
        limit = int(self.bar_settings.get("status_icon_limit", 14) or 14)
        limit = max(4, min(48, limit))
        overflow_manual: list[QWidget] = []
        visible_candidates: list[QWidget] = []
        for widget in self._status_managed_widgets:
            if widget is None:
                continue
            key = str(widget.property("statusKey") or "").strip()
            if widget.isHidden():
                continue
            if key and key in self._status_manual_overflow:
                overflow_manual.append(widget)
            else:
                visible_candidates.append(widget)

        if vertical_mode:
            net_widgets: list[QWidget] = []
            other_widgets: list[QWidget] = []
            for widget in visible_candidates:
                if str(widget.property("statusKey") or "").strip() == "net_icon":
                    net_widgets.append(widget)
                else:
                    other_widgets.append(widget)
            main_widgets = net_widgets[:1]
            overflow_widgets = overflow_manual + other_widgets + net_widgets[1:]
        else:
            service_order_raw = self.bar_settings.get("service_icon_order", [])
            service_order = (
                [str(item).strip() for item in service_order_raw if str(item).strip()]
                if isinstance(service_order_raw, list)
                else []
            )
            if service_order:
                rank = {key: index for index, key in enumerate(service_order)}
                slots: list[int] = []
                sortable: list[tuple[QWidget, int, int]] = []
                for index, widget in enumerate(visible_candidates):
                    status_key = str(widget.property("statusKey") or "").strip()
                    service_key = status_key.split(":", 1)[-1] if status_key else ""
                    if service_key in rank:
                        slots.append(index)
                        sortable.append((widget, rank[service_key], len(sortable)))
                if slots and sortable:
                    sortable.sort(key=lambda item: (item[1], item[2]))
                    for index, slot in enumerate(slots):
                        visible_candidates[slot] = sortable[index][0]

            main_widgets = visible_candidates[:limit]
            overflow_widgets = overflow_manual + visible_candidates[limit:]

        insert_anchor = (
            self.btn_clip if hasattr(self, "btn_clip") else self._status_overflow_button
        )
        for widget in main_widgets:
            if vertical_mode:
                anchor_index = self.status_layout.indexOf(self._status_overflow_button)
                if anchor_index < 0:
                    anchor_index = 0
            else:
                anchor_index = self.status_layout.indexOf(insert_anchor)
                if anchor_index < 0:
                    anchor_index = max(
                        0, self.status_layout.indexOf(self._status_overflow_button)
                    )
            self.status_layout.insertWidget(
                max(0, anchor_index),
                widget,
            )
            widget.show()
        for widget in overflow_widgets:
            self._status_overflow_layout.addWidget(widget)
            widget.show()

        has_overflow = len(overflow_widgets) > 0
        self._status_overflow_button.setVisible(True)
        if not has_overflow and self._status_overflow_open:
            self._status_overflow_popup.hide()
            self._status_overflow_open = False
        self._status_overflow_button.setEnabled(has_overflow)
        if vertical_mode:
            self._status_overflow_button.setText("↑↓")
        else:
            icon_name = "expand_more" if self._status_overflow_open else "expand_less"
            self._status_overflow_button.setText(self._icon_text(icon_name))

    def _bar_plugin_api(self, plugin_dir: Path) -> dict[str, object]:
        return {
            "plugin_dir": plugin_dir,
            "material_icon": material_icon,
            "load_service_settings": load_service_settings,
            "toggle_singleton_process": self._toggle_singleton_process,
            "sync_popup_button": self._sync_popup_button,
            "apply_icon": self._apply_icon_to_widget,
            "python_bin": self._python_bin,
            "register_hook": self._register_bar_plugin_hook,
            "add_status_button": self._add_status_plugin_button,
            "set_status_tooltip": self._set_status_widget_tooltip,
            "polkit_available": polkit_available,
            "build_polkit_command": build_polkit_command,
            "run_with_polkit": run_with_polkit,
            "trigger_fullscreen_alert": trigger_fullscreen_alert,
        }

    def _load_bar_plugins(self) -> None:
        for entrypoint in discover_bar_plugin_entrypoints():
            path_key = str(entrypoint.resolve())
            if path_key in self._loaded_bar_plugin_paths:
                continue
            module_name = f"hanauta_bar_plugin_{hash(str(entrypoint)) & 0xFFFFFFFF:x}"
            plugin_path = str(entrypoint.parent)
            path_added = False
            try:
                if plugin_path and plugin_path not in sys.path:
                    sys.path.insert(0, plugin_path)
                    path_added = True
                spec = importlib.util.spec_from_file_location(
                    module_name, str(entrypoint)
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                plugin_key = str(getattr(module, "SERVICE_KEY", "")).strip().lower()
                if plugin_key and plugin_key in self._loaded_bar_plugin_ids:
                    continue
                register = getattr(module, "register_hanauta_bar_plugin", None)
                if not callable(register):
                    continue
                register(self, self._bar_plugin_api(entrypoint.parent))
                self._loaded_bar_plugin_paths.add(path_key)
                if plugin_key:
                    self._loaded_bar_plugin_ids.add(plugin_key)
            except Exception:
                continue
            finally:
                if path_added:
                    try:
                        sys.path.remove(plugin_path)
                    except ValueError:
                        pass

    def _font_supports_text(self, font: QFont, text: str) -> bool:
        if not text:
            return False
        metrics = QFontMetrics(font)
        for char in text:
            if char.isspace():
                continue
            if not metrics.inFontUcs4(ord(char)):
                return False
        return True

    def _custom_icon_font(self, text: str, size: int) -> QFont | None:
        families = [
            self.reminders_font,
            "Symbols Nerd Font Mono",
            "Symbols Nerd Font",
            "JetBrainsMono Nerd Font Mono",
            "JetBrainsMono Nerd Font",
            "FiraCode Nerd Font Mono",
            "FiraCode Nerd Font",
            self.ui_font,
        ]
        seen: set[str] = set()
        for family in families:
            if not family or family in seen:
                continue
            seen.add(family)
            font = QFont(family, size)
            if self._font_supports_text(font, text):
                return font
        return None

    def _icon_font_for_text(
        self, icon_key: str, text: str, fallback_text: str, size: int
    ) -> tuple[QFont, bool, str]:
        override = self._bar_icon_overrides.get(icon_key, "").strip()
        if override and text == override:
            if icon_key == "launcher_note":
                return QFont(self.ui_font, size), False, text
            custom_font = self._custom_icon_font(text, size)
            if custom_font is not None:
                return custom_font, True, text
            # Fallback to the built-in Material icon when the override glyph is unsupported.
            return QFont(self.material_font, size), False, fallback_text
        return QFont(self.material_font, size), False, text

    def _apply_icon_to_widget(
        self, widget: QWidget, icon_key: str, fallback_text: str, size: int = 16
    ) -> None:
        override = self._bar_icon_overrides.get(icon_key, "").strip()
        if override:
            path = Path(os.path.expanduser(override))
            if path.exists() and path.is_file():
                if isinstance(widget, QPushButton):
                    widget.setProperty("iconKey", icon_key)
                    widget.setProperty("nerdIcon", False)
                    widget.setFont(QFont(self.material_font, size))
                    widget.setText("")
                    widget.setIcon(QIcon(str(path)))
                    widget.setIconSize(QSize(size, size))
                    return
                if isinstance(widget, QLabel):
                    widget.setProperty("iconKey", icon_key)
                    widget.setFont(QFont(self.material_font, size))
                    pixmap = QPixmap(str(path)).scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    widget.setPixmap(pixmap)
                    return
        if isinstance(widget, QPushButton):
            text = override or fallback_text
            font, nerd_icon, resolved_text = self._icon_font_for_text(
                icon_key, text, fallback_text, size
            )
            widget.setProperty("iconKey", icon_key)
            widget.setProperty("nerdIcon", nerd_icon)
            widget.setFont(font)
            widget.setIcon(QIcon())
            widget.setText(resolved_text)
        elif isinstance(widget, QLabel):
            text = override or fallback_text
            font, _, resolved_text = self._icon_font_for_text(
                icon_key, text, fallback_text, size
            )
            widget.setProperty("iconKey", icon_key)
            widget.setFont(font)
            widget.setPixmap(QPixmap())
            widget.setText(resolved_text)

    def _wrap_movable(self, widget: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return wrap

    def _setup_settings_watcher(self) -> None:
        self._settings_watcher = QFileSystemWatcher(self)
        self._settings_reload_timer = QTimer(self)
        self._settings_reload_timer.setSingleShot(True)
        self._settings_reload_timer.timeout.connect(self._reload_settings_from_watcher)
        self._mail_db_timer = QTimer(self)
        self._mail_db_timer.setSingleShot(True)
        self._mail_db_timer.timeout.connect(self._poll_mail_state)
        self._settings_watcher.fileChanged.connect(self._queue_settings_reload)
        self._settings_watcher.fileChanged.connect(self._queue_mail_poll)
        self._watch_settings_file()

    def _watch_settings_file(self) -> None:
        if self._settings_watcher is None:
            return
        watched_files = self._settings_watcher.files()
        if watched_files:
            self._settings_watcher.removePaths(watched_files)
        ensure_bar_icon_config()
        if SETTINGS_FILE.exists():
            self._settings_watcher.addPath(str(SETTINGS_FILE))
        if BAR_ICON_CONFIG_FILE.exists():
            self._settings_watcher.addPath(str(BAR_ICON_CONFIG_FILE))
        if MAIL_DB_PATH.exists():
            self._settings_watcher.addPath(str(MAIL_DB_PATH))

    def _queue_settings_reload(self) -> None:
        if self._settings_reload_timer is None:
            return
        self._settings_reload_timer.start(40)

    def _queue_mail_poll(self) -> None:
        if self._mail_db_timer is None:
            return
        self._mail_db_timer.start(40)

    def _setup_mail_notification_bus(self) -> None:
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return
        interface = QDBusInterface(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            bus,
        )
        if not interface.isValid():
            return
        self._mail_notification_interface = interface
        bus.connect(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "ActionInvoked",
            self._handle_mail_notification_action,
        )
        bus.connect(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "NotificationClosed",
            self._handle_mail_notification_closed,
        )

    def _reload_settings_from_watcher(self) -> None:
        self._watch_settings_file()
        self._reload_settings_if_needed(force=True)

    def _apply_vertical_offset(self, wrapper: QWidget, offset: int) -> None:
        layout = wrapper.layout()
        if layout is None:
            return
        layout.setContentsMargins(0, max(0, offset), 0, max(0, -offset))
        wrapper.updateGeometry()

    def _install_debug_tooltips(self) -> None:
        self.setToolTip("CyberBar root")
        self.ai_button.setToolTip("AI toggle button")
        self.launcher_trigger.setToolTip("Launcher button")
        self.workspace_chip.setToolTip("Workspace chip")
        self.workspace_label.setToolTip("Workspace label")
        self.datetime_chip.setToolTip("Date/time chip")
        self.weather_icon.setToolTip("Weather button")
        self.time_label.setToolTip("Time label")
        self.date_label.setToolTip("Date label / calendar")
        self.health_pill.setToolTip("Health")
        self.updates_pill.setToolTip("Updates")
        self.btn_control_center.setToolTip("Control center button")
        self.media_chip.setToolTip("Media chip")
        self.media_icon.setToolTip("Media icon")
        self.media_equalizer.setToolTip("Media equalizer")
        self.media_text.setToolTip("Media text")
        self.media_prev.setToolTip("Media previous button")
        self.media_play.setToolTip("Media play/pause button")
        self.media_next.setToolTip("Media next button")
        self.status_chip.setToolTip("Connectivity chip")
        self.net_icon.setToolTip("Wi-Fi button")
        self.vpn_icon.setToolTip("VPN button")
        self.christian_button.setToolTip("Christian widget button")
        self.reminders_button.setToolTip("Reminders widget button")
        self.mail_wrap.setToolTip("Mail")
        self.mail_button.setToolTip("Mail")
        self.mail_count.setToolTip("Unread mail count")
        self.ntfy_button.setToolTip("ntfy publisher button")
        self.caffeine_icon.setToolTip("Caffeine icon")
        self.battery_icon.setToolTip("Battery icon")
        self.battery_value.setToolTip("Battery value")
        self.btn_clip.setToolTip("Clipboard button")
        self.tray_host.setToolTip("Qt StatusNotifier tray")
        self.btn_power.setToolTip("Power button")

    def _clear_debug_tooltips(self) -> None:
        self.setToolTip("")
        self.ai_button.setToolTip("")
        self.launcher_trigger.setToolTip("")
        self.workspace_chip.setToolTip("")
        self.workspace_label.setToolTip("")
        self.datetime_chip.setToolTip("")
        self.weather_icon.setToolTip("")
        self.time_label.setToolTip("")
        self.date_label.setToolTip("")
        self.health_pill.setToolTip("")
        self.updates_pill.setToolTip("")
        self.btn_control_center.setToolTip("")
        self.media_chip.setToolTip("")
        self.media_icon.setToolTip("")
        self.media_equalizer.setToolTip("")
        self.media_text.setToolTip("")
        self.media_prev.setToolTip("")
        self.media_play.setToolTip("")
        self.media_next.setToolTip("")
        self.status_chip.setToolTip("")
        self.net_icon.setToolTip("")
        self.vpn_icon.setToolTip("")
        self.christian_button.setToolTip("")
        self.reminders_button.setToolTip("")
        self.mail_wrap.setToolTip("")
        self.mail_button.setToolTip("")
        self.mail_count.setToolTip("")
        self.ntfy_button.setToolTip("")
        self.caffeine_icon.setToolTip("")
        self.battery_icon.setToolTip("")
        self.battery_value.setToolTip("")
        self.btn_clip.setToolTip("")
        self.tray_host.setToolTip("")
        self.btn_power.setToolTip("")

    def _set_status_widget_tooltip(self, key: str, tooltip: str) -> None:
        status_key = str(key).strip()
        if not status_key:
            return
        text = str(tooltip).strip()
        for widget in self._status_managed_widgets:
            current = str(widget.property("statusKey") or "").strip()
            if not current:
                continue
            service_key = current.split(":", 1)[-1]
            if current == status_key or service_key == status_key:
                widget.setToolTip(text)

    def _apply_installed_widget_tooltips(self) -> None:
        marketplace = self.runtime_settings.get("marketplace", {})
        installed = (
            marketplace.get("installed_plugins", [])
            if isinstance(marketplace, dict)
            else []
        )
        if not isinstance(installed, list):
            return
        for row in installed:
            if not isinstance(row, dict):
                continue
            plugin_id = str(row.get("id", "")).strip()
            plugin_name = str(row.get("name", "")).strip()
            if not plugin_id or not plugin_name:
                continue
            # In normal mode, widget tooltips should only show the widget/plugin name.
            self._set_status_widget_tooltip(plugin_id, plugin_name)

    def _apply_debug_tooltips_setting(self) -> None:
        if bool(self.bar_settings.get("debug_tooltips", False)):
            self._install_debug_tooltips()
        else:
            self._clear_debug_tooltips()
            self._apply_installed_widget_tooltips()

    def _enforce_plugin_icon_mode(self) -> None:
        if bool(self.bar_settings.get("use_color_widget_icons", False)):
            return
        tint = self._widget_icon_tint_color()
        for button in self.findChildren(QPushButton):
            if button.objectName() != "statusIconButton":
                continue
            if not isinstance(button, QPushButton):
                continue
            icon = button.icon()
            if icon.isNull():
                continue
            size = button.iconSize()
            target = max(12, int(size.width() if size.width() > 0 else 16))
            tinted = tinted_qicon(icon, tint, target)
            if tinted.isNull():
                continue
            button.setIcon(tinted)

    def _apply_bar_settings(self) -> None:
        self.bar_settings = load_bar_settings()
        self._rebuild_workspace_buttons()
        self.workspace_label.setVisible(
            bool(self.bar_settings.get("show_workspace_label", False))
        )
        orientation = self._bar_orientation_mode()
        vertical_mode = orientation in {"vertical_left", "vertical_right"}
        merge_all_chips = bool(self.bar_settings.get("merge_all_chips", False))
        bar_height = int(self.bar_settings.get("bar_height", 40))
        outer_vertical_margin = 4
        surface_height = max(24, bar_height - (outer_vertical_margin * 2))
        chip_height = max(22, surface_height - 2)
        chip_vertical_padding = max(4, min(14, (surface_height - 22) // 2))
        self._position_on_target_screen(bar_height)
        if vertical_mode:
            self.outer_layout.setContentsMargins(4, 12, 4, 12)
            self.bar_surface.setMinimumHeight(0)
            self.bar_surface.setMaximumHeight(16777215)
            self.bar_surface.setFixedWidth(max(24, self.width() - 8))
            self.root_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.root_layout.setSpacing(0 if merge_all_chips else 8)
            self.root_layout.setContentsMargins(1, 8, 1, 8)
        else:
            self.outer_layout.setContentsMargins(
                12, outer_vertical_margin, 12, outer_vertical_margin
            )
            self.bar_surface.setMinimumWidth(0)
            self.bar_surface.setMaximumWidth(16777215)
            self.bar_surface.setFixedHeight(surface_height)
            self.root_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.root_layout.setSpacing(0 if merge_all_chips else 14)
            self.root_layout.setContentsMargins(8, 1, 8, 1)
        self.left_layout.setSpacing(0 if merge_all_chips else 10)
        self.center_layout.setSpacing(0 if merge_all_chips else 10)
        self.right_layout.setSpacing(0 if merge_all_chips else 8)
        for chip in (
            self.launcher_chip,
            self.workspace_chip,
            self.datetime_chip,
            self.media_chip,
            self.cap_alert_chip,
            self.status_chip,
        ):
            chip.setFixedHeight(chip_height)
        self.launcher_layout.setContentsMargins(
            8, chip_vertical_padding, 8, chip_vertical_padding
        )
        self.workspace_layout.setContentsMargins(
            12, chip_vertical_padding, 12, chip_vertical_padding
        )
        self.datetime_layout.setContentsMargins(
            12, chip_vertical_padding, 12, chip_vertical_padding
        )
        self.media_layout.setContentsMargins(
            14, chip_vertical_padding, 14, chip_vertical_padding
        )
        self.status_layout.setContentsMargins(
            10, chip_vertical_padding, 10, chip_vertical_padding
        )
        self.cap_alert_glow_frame.setGeometry(self.cap_alert_chip.rect())
        self._apply_vertical_offset(
            self.ai_wrap, self.bar_settings.get("launcher_offset", 0)
        )
        self._apply_vertical_offset(
            self.launcher_wrap, self.bar_settings.get("launcher_offset", 0)
        )
        self._apply_vertical_offset(
            self.workspace_wrap, self.bar_settings.get("workspace_offset", 0)
        )
        self._apply_vertical_offset(
            self.datetime_wrap, self.bar_settings.get("datetime_offset", 0)
        )
        self._apply_vertical_offset(
            self.media_wrap, self.bar_settings.get("media_offset", 0)
        )
        self._apply_vertical_offset(
            self.status_wrap, self.bar_settings.get("status_offset", 0)
        )
        self._apply_vertical_offset(
            self.tray_wrap, self.bar_settings.get("tray_offset", 0)
        )
        if vertical_mode:
            self.root_layout.setAlignment(
                self.left_wrap_widget,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )
            self.root_layout.setAlignment(
                self.center_wrap_widget,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )
            self.root_layout.setAlignment(
                self.right_wrap_widget,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )
        else:
            self.root_layout.setAlignment(
                self.left_wrap_widget,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self.root_layout.setAlignment(
                self.center_wrap_widget,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            )
            self.root_layout.setAlignment(
                self.right_wrap_widget,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
        self._sync_status_overflow()

    def _rebuild_workspace_buttons(self) -> None:
        if not hasattr(self, "dots_layout"):
            return
        while self.dots_layout.count():
            item = self.dots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.workspace_buttons.clear()
        workspace_count = int(self.bar_settings.get("workspace_count", 5) or 5)
        for ws_num in range(1, workspace_count + 1):
            dot = WorkspaceDot(ws_num, self._goto_workspace)
            self.workspace_buttons[ws_num] = dot
            self.dots_layout.addWidget(dot)

    def _apply_styles(self) -> None:
        theme = self.theme
        chip_radius = int(self.bar_settings.get("chip_radius", 0))
        chip_radius_css = f"{chip_radius}px"
        merge_all_chips = bool(self.bar_settings.get("merge_all_chips", False))
        full_bar_radius = int(self.bar_settings.get("full_bar_radius", 18))
        full_bar_radius_css = f"{full_bar_radius}px"
        status_icon_color = theme.primary
        status_hover_color = theme.text
        status_active_color = theme.primary
        use_color_widget_icons = bool(
            self.bar_settings.get("use_color_widget_icons", False)
        )
        tint_tray_icons = (not use_color_widget_icons) or (
            bool(self.bar_settings.get("tray_tint_with_matugen", True))
            and bool(theme.use_matugen)
        )
        self.tray_host.set_icon_tint(QColor(theme.primary) if tint_tray_icons else None)
        chip_bg = (
            "transparent"
            if merge_all_chips
            else rgba(theme.surface_container_high, 0.78)
        )
        chip_border = "transparent" if merge_all_chips else rgba(theme.outline, 0.18)
        media_bg = (
            "transparent" if merge_all_chips else rgba(theme.surface_container, 0.86)
        )
        media_border = "transparent" if merge_all_chips else rgba(theme.outline, 0.20)
        full_bar_bg = (
            rgba(theme.surface_container, 0.90) if merge_all_chips else "transparent"
        )
        full_bar_border = (
            rgba(theme.outline, 0.20) if merge_all_chips else "transparent"
        )
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "{self.ui_font}";
                font-size: 12px;
            }}
            #barSurface {{
                background: {full_bar_bg};
                border: 1px solid {full_bar_border};
                border-radius: {full_bar_radius_css};
            }}
            #workspaceChip, #dateTimeChip, #launcherChip {{
                background: {chip_bg};
                border: 1px solid {chip_border};
                border-radius: {chip_radius_css};
            }}
            #mediaChip {{
                background: {media_bg};
                border: 1px solid {media_border};
                border-radius: {chip_radius_css};
            }}
            #mediaChip[active="false"] {{
                background: {"transparent" if merge_all_chips else theme.chip_bg};
                border: 1px solid {"transparent" if merge_all_chips else theme.chip_border};
            }}
            #connectivityChip {{
                background: {media_bg};
                border: 1px solid {media_border};
                border-radius: {chip_radius_css};
            }}
            #updatesPill {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            #healthPill {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            #updatesPillIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
                font-size: 14px;
            }}
            #healthPillIcon {{
                color: {theme.primary};
                font-family: "{self.material_font}";
                font-size: 14px;
            }}
            #updatesPillCount {{
                color: {theme.text};
                font-size: 10px;
                font-weight: 700;
            }}
            #healthPillValue {{
                color: {theme.text};
                font-size: 10px;
                font-weight: 700;
            }}
            #healthPill:hover {{
                background: {theme.hover_bg};
                border-radius: 11px;
            }}
            #updatesPill:hover {{
                background: {theme.hover_bg};
                border-radius: 11px;
            }}
            #capAlertChip {{
                background: {rgba("#f6cf5a", 0.30)};
                border: 1px solid {rgba("#f6cf5a", 0.58)};
                border-radius: {chip_radius_css};
            }}
            #capAlertGlow {{
                background: transparent;
                border: 2px solid rgba(255, 224, 120, 0.45);
                border-radius: {max(8, chip_radius)}px;
            }}
            #capAlertChip:hover {{
                background: {rgba("#f6cf5a", 0.38)};
                border: 1px solid {rgba("#ffd54f", 0.76)};
            }}
            #launcherTrigger {{
                background: transparent;
                border: none;
                border-radius: {max(0, chip_radius - 4)}px;
                min-height: 20px;
                max-height: 20px;
            }}
            QLabel#launcherNote {{
                font-family: "{self.ui_font}";
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.3px;
                padding-bottom: 2px;
            }}
            QLabel#launcherText {{
                font-family: "{self.ui_font}";
                font-size: 12px;
                font-weight: 650;
                letter-spacing: 0.7px;
                padding-bottom: 0px;
            }}
            #workspaceLabel {{
                color: {theme.text_muted};
                font-weight: 500;
            }}
            #statusIcon {{
                font-family: "{self.material_font}";
                color: {status_icon_color};
            }}
            #mediaIcon {{
                font-family: "{self.material_font}";
                color: {theme.secondary};
            }}
            #statusIconButton {{
                background: transparent;
                border: none;
                color: {status_icon_color};
                font-family: "{self.material_font}";
                min-width: 22px;
                max-width: 22px;
                padding: 0;
            }}
            #statusIconButton:hover {{
                color: {status_hover_color};
                background: {theme.hover_bg};
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #statusIconButton:checked {{
                color: {status_active_color};
                background: {theme.accent_soft};
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #statusIconButton[active="true"] {{
                color: {status_active_color};
            }}
            #statusIconButton[nerdIcon="true"] {{
                font-family: "{self.reminders_font}";
            }}
            #mailStatusWrap {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            #mailUnreadCount {{
                background: transparent;
                color: {theme.text_muted};
                border: none;
                min-width: 0px;
                padding: 0;
                font-size: 10px;
                font-weight: 700;
            }}
            #capAlertWarning {{
                color: #ffd95a;
                font-family: "{self.material_font}";
                font-size: 17px;
            }}
            #capAlertText {{
                color: #fff9e8;
                font-size: 11px;
                font-weight: 700;
            }}
            #statusLockButton {{
                background: transparent;
                border: 1px solid transparent;
                color: {theme.inactive};
                min-width: 26px;
                max-width: 26px;
                padding: 0;
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #statusLockButton[active="true"] {{
                background: {rgba(theme.primary, 0.14)};
                color: {theme.primary};
                border: 1px solid {rgba(theme.primary, 0.18)};
            }}
            #statusLockButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            #mediaText {{
                color: {theme.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            #mediaChip[active="true"] QLabel#mediaText {{
                color: {theme.text};
            }}
            #mediaChip[active="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme.media_active_start},
                    stop:1 {theme.media_active_end});
                border: 1px solid {theme.media_active_border};
            }}
            #mediaChip[active="true"] QLabel#mediaIcon {{
                color: {theme.primary};
            }}
            #equalizerWrap {{
                background: transparent;
            }}
            #mediaControl {{
                background: transparent;
                border: none;
                color: {theme.secondary};
                font-family: "{self.material_font}";
                min-width: 22px;
                max-width: 22px;
                padding: 0;
            }}
            #mediaChip[active="true"] QPushButton#mediaControl {{
                color: {theme.primary};
            }}
            #utilityButton {{
                background: transparent;
                border: none;
                color: {theme.inactive};
                font-family: "{self.material_font}";
                min-width: 22px;
                max-width: 22px;
                padding: 0;
            }}
            #regionButton {{
                background: transparent;
                border: none;
                color: {theme.primary};
                font-family: "{self.material_font}";
                min-width: 22px;
                max-width: 22px;
                padding: 0;
            }}
            #mediaControl:hover, #utilityButton:hover {{
                color: {theme.text};
                background: {theme.hover_bg};
                border-radius: 11px;
            }}
            #regionButton:hover {{
                color: {theme.text};
                background: {theme.hover_bg};
                border-radius: 11px;
            }}
            #utilityButton:checked {{
                color: {theme.primary};
                background: {theme.accent_soft};
                border-radius: 11px;
            }}
            #aiToggleButton {{
                background: transparent;
                border: none;
                color: {theme.primary};
                font-family: "{self.material_font}";
                min-width: 28px;
                max-width: 28px;
                min-height: 24px;
                max-height: 24px;
                padding: 1px 0 0 0;
                outline: none;
            }}
            #launcherChip QPushButton#aiToggleButton:hover {{
                background: transparent;
                border: none;
                color: {theme.primary};
                outline: none;
            }}
            #launcherChip QPushButton#aiToggleButton:focus {{
                background: transparent;
                border: none;
                outline: none;
            }}
            #launcherChip QFrame#launcherTrigger:hover {{
                background: transparent;
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #launcherChip QFrame#launcherTrigger:hover QLabel#launcherNote,
            #launcherChip QFrame#launcherTrigger:hover QLabel#launcherText {{
                color: {theme.text_muted};
            }}
            #aiToggleButton:checked {{
                color: {theme.primary};
                background: {theme.accent_soft};
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #timeLabel {{
                color: {theme.primary};
                font-size: 12px;
                font-weight: 600;
                padding-right: 2px;
            }}
            #dateLabel {{
                color: {theme.secondary};
                font-size: 10px;
                font-weight: 600;
            }}
            #batteryValue {{
                background: {theme.battery_bg};
                color: {theme.battery_text};
                border-radius: 9px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            }}
            QFrame#trayHost {{
                background: {theme.tray_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
            }}
            QFrame#trayHost[embedded="true"] {{
                background: transparent;
                border: none;
                border-radius: 0;
            }}
            QFrame#statusOverflowPopup {{
                background: {rgba(theme.surface_container_high, 0.96)};
                border: 1px solid {rgba(theme.outline, 0.34)};
                border-radius: 12px;
            }}
            QPushButton#trayButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                color: {status_icon_color};
                font-size: 11px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton#trayButton:hover {{
                background: {theme.hover_bg};
                color: {status_hover_color};
            }}
            """
        )
        self._update_launcher_wordmark_colors()
        for dot in self.workspace_buttons.values():
            dot.set_colors(
                {
                    "focused": theme.workspace_focused,
                    "occupied": theme.workspace_occupied,
                    "urgent": theme.workspace_urgent,
                    "empty": theme.workspace_empty,
                }
            )
        self._update_media_equalizer_color()
        self._set_vpn_button_icon(bool(self.vpn_icon.property("active")))
        self._set_christian_button_icon()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_mail_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_desktop_clock_process()
        self._update_locale_button()
        self._update_window_mask()

    def _update_launcher_wordmark_colors(self, hovered: bool = False) -> None:
        del hovered
        note_color = self.theme.primary
        text_color = self.theme.text_muted
        self.launcher_note.setStyleSheet(f"color: {note_color};")
        self.launcher_text.setStyleSheet(f"color: {text_color};")

    def _format_time_text(self, moment: datetime) -> str:
        if bool(self.region_settings.get("use_24_hour", False)):
            return moment.strftime("%H:%M")
        return moment.strftime("%-I:%M %p")

    def _format_date_text(self, moment: datetime) -> str:
        style = str(self.region_settings.get("date_style", "us"))
        if style == "iso":
            return moment.strftime("%a, %Y-%m-%d")
        if style == "eu":
            return moment.strftime("%a, %d/%m")
        return moment.strftime("%a, %m/%d")

    def _update_locale_button(self) -> None:
        locale_code = str(self.region_settings.get("locale_code", "")).strip()
        label = locale_code or "System locale"
        self.locale_button.setToolTip(f"Region & locale: {label}")

    def _set_lock_button_state(
        self, button: QPushButton, active: bool, title: str
    ) -> None:
        button.setProperty("active", active)
        button.setVisible(active)
        button.setToolTip(f"{title}: {'On' if active else 'Off'}")
        self.style().unpolish(button)
        self.style().polish(button)

    def _lock_keys_plugin_owns_bar(self) -> bool:
        service = self.service_settings.get("lock_keys_osd", {})
        if not isinstance(service, dict):
            return False
        return bool(service.get("enabled", False))

    def _send_lock_notification(
        self, title: str, enabled: bool, replace_id: int
    ) -> None:
        state_text = "Enabled" if enabled else "Disabled"
        try:
            subprocess.Popen(
                [
                    "notify-send",
                    "-a",
                    "Hanauta Bar",
                    "-r",
                    str(replace_id),
                    title,
                    state_text,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _update_media_equalizer_color(self) -> None:
        color = self.theme.equalizer if self._media_playing else self.theme.text_muted
        for bar in getattr(self, "equalizer_bars", []):
            bar.set_color(color)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            self._reload_settings_if_needed()
            return
        previous_use_matugen = bool(getattr(self, "_theme_use_matugen", False))
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._theme_use_matugen = bool(self.theme.use_matugen)
        new_signature = (
            theme_font_family("ui"),
            theme_font_family("display"),
            theme_font_family("mono"),
        )
        if new_signature != getattr(self, "_theme_font_signature", ("", "", "")):
            self._theme_font_signature = new_signature
            self._restart_for_theme_refresh()
            return
        self._apply_styles()
        self._reload_settings_if_needed(force=True)
        if previous_use_matugen != self._theme_use_matugen:
            self._restart_desktop_clock_for_theme_change()

    def _restart_for_theme_refresh(self) -> None:
        if getattr(self, "_theme_refresh_restart_pending", False):
            return
        self._theme_refresh_restart_pending = True
        subprocess.Popen(
            [python_executable(), str(Path(__file__).resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        QTimer.singleShot(0, self.close)

    def _reload_settings_if_needed(self, force: bool = False) -> None:
        current_mtime = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        icon_mtime = (
            BAR_ICON_CONFIG_FILE.stat().st_mtime
            if BAR_ICON_CONFIG_FILE.exists()
            else 0.0
        )
        icon_changed = getattr(self, "_bar_icon_mtime", 0.0) != icon_mtime
        if not force and current_mtime == self._settings_mtime and not icon_changed:
            return
        self._settings_mtime = current_mtime
        self._bar_icon_mtime = icon_mtime
        self._bar_icon_overrides = load_bar_icon_overrides()
        self.runtime_settings = normalize_runtime_settings(load_runtime_settings())
        services = self.runtime_settings.get("services", {})
        self.service_settings = services if isinstance(services, dict) else {}
        self.region_settings = load_region_settings()
        self.bar_settings = load_bar_settings_from_payload(self.runtime_settings)
        self.autolock_settings = load_autolock_settings_from_payload(
            self.runtime_settings
        )
        self._load_bar_plugins()
        self._apply_bar_settings()
        self._apply_bar_icon_overrides()
        self._apply_styles()
        self._run_bar_plugin_hooks("settings_reloaded")
        self._enforce_plugin_icon_mode()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_mail_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._sync_status_overflow()
        self._sync_cap_alert_chip()
        self._apply_debug_tooltips_setting()
        self._poll_cap_alerts()
        self._sync_desktop_clock_process()
        self._update_locale_button()

    def _apply_bar_icon_overrides(self) -> None:
        self._apply_icon_to_widget(
            self.locale_button, "public", material_icon("public"), 16
        )
        self._apply_icon_to_widget(
            self.media_icon, "music_note", material_icon("music_note"), 16
        )
        self._set_pomodoro_button_icon()
        self._set_reminders_button_icon()
        self._set_rss_button_icon()
        self._set_obs_button_icon()
        self._set_crypto_button_icon()
        self._apply_icon_to_widget(self.mail_button, "mail", material_icon("mail"), 16)
        self._set_ntfy_button_icon()
        self._set_game_mode_button_icon()
        self._run_bar_plugin_hooks("icons")
        self._enforce_plugin_icon_mode()
        # Keep host-managed widget icons aligned with the current icon mode,
        # even if plugin hooks set their own icon assets.
        self._set_pomodoro_button_icon()
        self._set_reminders_button_icon()
        self._set_rss_button_icon()
        self._set_ntfy_button_icon()
        self._apply_icon_to_widget(
            self.caffeine_icon, "coffee", material_icon("coffee"), 16
        )
        self._set_clipboard_button_icon()
        self._apply_icon_to_widget(
            self.btn_power,
            "power_settings_new",
            material_icon("power_settings_new"),
            20,
        )
        self._apply_icon_to_widget(self.launcher_note, "launcher_note", "♪", 14)
        self._set_vpn_button_icon(self.vpn_icon.property("active") == True)
        self._set_christian_button_icon()
        self._enforce_plugin_icon_mode()
        apply_antialias_font(self)

    def _update_window_mask(self) -> None:
        self.setMask(QRegion(self.rect()))

    def _start_polls(self) -> None:
        self._clear_game_mode_popup_process()
        self._poll_all()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._poll_clock)
        self.clock_timer.start(1000)

        self.workspace_timer = QTimer(self)
        self.workspace_timer.timeout.connect(self._poll_workspaces)
        self.workspace_timer.start(1200)

        self.media_timer = QTimer(self)
        self.media_timer.timeout.connect(self._poll_media)
        self.media_timer.start(2000)

        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self._poll_system)
        self.system_timer.start(5000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self.updates_timer = QTimer(self)
        self.updates_timer.timeout.connect(self._poll_updates_count)
        self.updates_timer.start(15 * 60 * 1000)
        QTimer.singleShot(1200, self._poll_updates_count)

        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._poll_health_snapshot)
        self.health_timer.start(10 * 60 * 1000)
        QTimer.singleShot(900, self._poll_health_snapshot)

        self.settings_timer = QTimer(self)
        self.settings_timer.timeout.connect(self._reload_settings_if_needed)
        self.settings_timer.start(2000)

        self.autolock_timer = QTimer(self)
        self.autolock_timer.timeout.connect(self._poll_autolock)
        self.autolock_timer.start(5000)

        self.ai_popup_timer = QTimer(self)
        self.ai_popup_timer.timeout.connect(self._sync_ai_button)
        self.ai_popup_timer.start(2000)

        self.control_center_timer = QTimer(self)
        self.control_center_timer.timeout.connect(self._sync_control_center_button)
        self.control_center_timer.start(2000)

        self.wifi_popup_timer = QTimer(self)
        self.wifi_popup_timer.timeout.connect(self._sync_wifi_button)
        self.wifi_popup_timer.start(2000)

        self.vpn_popup_timer = QTimer(self)
        self.vpn_popup_timer.timeout.connect(self._sync_vpn_button)
        self.vpn_popup_timer.start(2000)

        self.ntfy_popup_timer = QTimer(self)
        self.ntfy_popup_timer.timeout.connect(self._sync_ntfy_button)
        self.ntfy_popup_timer.start(2000)

        self.game_mode_popup_timer = QTimer(self)
        self.game_mode_popup_timer.timeout.connect(self._sync_game_mode_button)
        self.game_mode_popup_timer.start(2000)

        self.plugin_poll_timer = QTimer(self)
        self.plugin_poll_timer.timeout.connect(self._run_plugin_poll_hooks)
        self.plugin_poll_timer.start(2000)

        self.weather_popup_timer = QTimer(self)
        self.weather_popup_timer.timeout.connect(self._sync_weather_button)
        self.weather_popup_timer.start(2000)

        self.obs_state_timer = QTimer(self)
        self.obs_state_timer.timeout.connect(self._poll_obs_state)
        self.obs_state_timer.start(5000)

        self.obs_flash_timer = QTimer(self)
        self.obs_flash_timer.timeout.connect(self._tick_obs_recording_flash)
        self.obs_flash_timer.start(550)

        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self._poll_weather)
        self.weather_timer.start(900000)

        self.equalizer_timer = QTimer(self)
        self.equalizer_timer.timeout.connect(self._render_equalizer_frame)
        self.equalizer_timer.start(16)

        self.cap_alert_timer = QTimer(self)
        self.cap_alert_timer.timeout.connect(self._poll_cap_alerts)
        self.cap_alert_timer.start(60000)

        self.cap_alert_pulse_timer = QTimer(self)
        self.cap_alert_pulse_timer.timeout.connect(self._tick_cap_alert_pulse)
        self.cap_alert_pulse_timer.start(90)

        self.rss_notify_timer = QTimer(self)
        self.rss_notify_timer.timeout.connect(self._poll_rss_notifications)
        self.rss_notify_timer.start(60000)

        self.crypto_timer = QTimer(self)
        self.crypto_timer.timeout.connect(self._poll_crypto_notifications)
        self.crypto_timer.start(60000)

        self.mail_timer = QTimer(self)
        self.mail_timer.timeout.connect(self._poll_mail_state)
        self.mail_timer.start(30000)

        self.powermenu_timer = QTimer(self)
        self.powermenu_timer.timeout.connect(self._sync_powermenu_button)
        self.powermenu_timer.start(2000)

        self._start_cava()

    def _clear_game_mode_popup_process(self) -> None:
        if GAME_MODE_POPUP is not None:
            for pattern in entry_patterns(GAME_MODE_POPUP):
                terminate_background_matches(pattern)

    def _poll_all(self) -> None:
        self._poll_clock()
        self._poll_workspaces()
        self._poll_media()
        self._poll_system()
        self._poll_weather()
        self._poll_cap_alerts()
        self._poll_rss_notifications()
        self._poll_crypto_notifications()
        self._poll_mail_state()
        self._poll_obs_state()
        self._sync_game_mode_button()
        self._run_plugin_poll_hooks()
        self._sync_status_overflow()

    def _run_plugin_poll_hooks(self) -> None:
        self._run_bar_plugin_hooks("poll")
        self._enforce_plugin_icon_mode()

    def _tree_has_window(self, titles: tuple[str, ...]) -> bool:
        raw = run_cmd(["i3-msg", "-t", "get_tree"])
        if not raw:
            return False
        try:
            tree = json.loads(raw)
        except Exception:
            return False

        normalized = {title.strip().lower() for title in titles if title.strip()}
        if not normalized:
            return False

        def search(node: dict) -> bool:
            if not isinstance(node, dict):
                return False
            title = str(node.get("name", "")).strip().lower()
            if title in normalized:
                return True
            props = node.get("window_properties")
            if isinstance(props, dict):
                window_name = str(props.get("name", "")).strip().lower()
                if window_name in normalized:
                    return True
            for key in ("nodes", "floating_nodes"):
                children = node.get(key)
                if isinstance(children, list):
                    for child in children:
                        if isinstance(child, dict) and search(child):
                            return True
            return False

        return bool(search(tree))

    def _poll_clock(self) -> None:
        now = datetime.now()
        self.time_label.setText(self._format_time_text(now))
        self.date_label.setText(self._format_date_text(now))

    def _poll_workspaces(self) -> None:
        if self._workspace_worker is not None and self._workspace_worker.isRunning():
            return
        self._workspace_worker = WorkspaceStateWorker()
        self._workspace_worker.loaded.connect(self._apply_workspace_state)
        self._workspace_worker.finished.connect(self._finish_workspace_worker)
        self._workspace_worker.start()

    def _poll_media(self) -> None:
        if self._media_worker is not None and self._media_worker.isRunning():
            return
        self._media_worker = MediaStateWorker()
        self._media_worker.loaded.connect(self._apply_media_state)
        self._media_worker.finished.connect(self._finish_media_worker)
        self._media_worker.start()

    def _apply_workspace_state(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        focused_num = int(payload.get("focused_num", 1) or 1)
        occupied = {
            int(item) for item in payload.get("occupied", []) if str(item).strip()
        }
        urgent = {int(item) for item in payload.get("urgent", []) if str(item).strip()}
        self._focused_workspace_has_real_windows = bool(
            payload.get("has_real_windows", False)
        )
        self.workspace_label.setText(f"Workspace {focused_num}")
        for ws_num, button in self.workspace_buttons.items():
            if ws_num in urgent:
                button.set_state("urgent")
            elif ws_num == focused_num:
                button.set_state("focused")
            elif ws_num in occupied:
                button.set_state("occupied")
            else:
                button.set_state("empty")
        self._sync_desktop_clock_process(self._focused_workspace_has_real_windows)

    def _finish_workspace_worker(self) -> None:
        self._workspace_worker = None

    def _apply_media_state(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        title = str(payload.get("title", "Play Something"))
        artist = str(payload.get("artist", "Artist"))
        status = str(payload.get("status", "Stopped"))
        has_media = bool(title and title != "Play Something")

        if has_media:
            display = f"{artist} - {title}" if artist else title
            self.media_text.setText(
                display[:42] + "…" if len(display) > 42 else display
            )
            self.media_play.setText(
                material_icon("pause" if status == "Playing" else "play_arrow")
            )
        else:
            self.media_text.setText("Nothing playing")
            self.media_play.setText(material_icon("play_arrow"))

        playing_now = status == "Playing" and has_media
        if playing_now != self._media_playing:
            self._media_playing = playing_now
            self.media_chip.setProperty("active", self._media_playing)
            self.style().unpolish(self.media_chip)
            self.style().polish(self.media_chip)
            self._update_media_equalizer_color()
        if has_media != self._media_visible:
            self._media_visible = has_media
            self._animate_media(has_media)

    def _finish_media_worker(self) -> None:
        self._media_worker = None

    def _animate_media(self, visible: bool) -> None:
        target = 1.0 if visible else 0.82
        if self._media_animation is not None:
            self._media_animation.stop()
        self._media_animation = QPropertyAnimation(self.media_opacity, b"opacity", self)
        self._media_animation.setDuration(220)
        self._media_animation.setStartValue(self.media_opacity.opacity())
        self._media_animation.setEndValue(target)
        self._media_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._media_animation.start()

    def _start_cava(self) -> None:
        if self._cava_worker is not None:
            self._cava_worker.stop()
            self._cava_worker.wait(500)
            self._cava_worker.deleteLater()
        self._cava_worker = CavaWorker(CAVA_BAR_CONFIG, len(self.equalizer_bars), self)
        self._cava_worker.frame_ready.connect(self._apply_cava_frame)
        self._cava_worker.stream_ended.connect(self._handle_cava_exit)
        self._cava_worker.finished.connect(self._finish_cava_worker)
        self._cava_worker.start()

    def _finish_cava_worker(self) -> None:
        worker = self.sender()
        if worker is self._cava_worker:
            self._cava_worker = None

    def _apply_cava_frame(self, frame: object) -> None:
        if isinstance(frame, list):
            parts = frame[: len(self.equalizer_bars)]
        elif isinstance(frame, tuple):
            parts = list(frame[: len(self.equalizer_bars)])
        else:
            return
        if not parts:
            return

        values: list[float] = []
        for part in parts:
            try:
                values.append(max(0.0, min(1.0, int(part) / 100.0)))
            except (TypeError, ValueError):
                values.append(0.0)

        if not self._media_playing:
            values = [0.08 for _ in values]

        if len(values) < len(self.equalizer_bars):
            values.extend([0.08] * (len(self.equalizer_bars) - len(values)))
        self._equalizer_targets = values[: len(self.equalizer_bars)]

    def _render_equalizer_frame(self) -> None:
        if not getattr(self, "equalizer_bars", None):
            return
        if not getattr(self, "_equalizer_targets", None):
            self._equalizer_targets = [0.08] * len(self.equalizer_bars)
        if not getattr(self, "_equalizer_levels", None):
            self._equalizer_levels = [0.08] * len(self.equalizer_bars)
        if len(self._equalizer_targets) != len(self.equalizer_bars):
            self._equalizer_targets = [0.08] * len(self.equalizer_bars)
        if len(self._equalizer_levels) != len(self.equalizer_bars):
            self._equalizer_levels = [0.08] * len(self.equalizer_bars)

        if not self._media_playing:
            self._equalizer_targets = [0.08] * len(self.equalizer_bars)

        for index, bar in enumerate(self.equalizer_bars):
            current = float(self._equalizer_levels[index])
            target = float(self._equalizer_targets[index])
            smoothing = 0.55 if target >= current else 0.35
            updated = current + ((target - current) * smoothing)
            if abs(updated - target) < 0.015:
                updated = target
            self._equalizer_levels[index] = updated
            bar.set_level(updated)

    def _handle_cava_exit(self) -> None:
        if self._closing:
            return
        QTimer.singleShot(1000, self._start_cava)

    def _poll_system(self) -> None:
        if (
            self._system_state_worker is not None
            and self._system_state_worker.isRunning()
        ):
            return
        self._system_state_worker = SystemStateWorker(self._battery_base, self)
        self._system_state_worker.loaded.connect(self._apply_system_state)
        self._system_state_worker.finished.connect(self._finish_system_state_worker)
        self._system_state_worker.start()
        poll_health_reminders()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_mail_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._run_bar_plugin_hooks("settings_reloaded")
        self._enforce_plugin_icon_mode()
        self._sync_health_pill_visibility()
        self._sync_weather_visibility()
        self._sync_cap_alert_chip()

    def _apply_system_state(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        connected = bool(payload.get("connected", False))
        self._apply_icon_to_widget(
            self.net_icon,
            "wifi" if connected else "wifi_off",
            material_icon("wifi" if connected else "wifi_off"),
            16,
        )

        wg_active = bool(payload.get("wg_active", False))
        selected_iface = str(payload.get("selected_iface", "")).strip()
        self._set_vpn_button_icon(wg_active)
        self.vpn_icon.setProperty("active", wg_active)
        self.vpn_icon.setToolTip(f"WireGuard: {selected_iface or 'No config selected'}")
        self.style().unpolish(self.vpn_icon)
        self.style().polish(self.vpn_icon)

        caffeine_on = bool(payload.get("caffeine_on", False))
        self.caffeine_icon.setVisible(caffeine_on)
        self._apply_icon_to_widget(
            self.caffeine_icon, "coffee", material_icon("coffee"), 16
        )

        caps_on = bool(payload.get("caps_on", False))
        num_on = bool(payload.get("num_on", False))
        if self._lock_keys_plugin_owns_bar():
            self.caps_lock_button.hide()
            self.num_lock_button.hide()
        else:
            self._set_lock_button_state(self.caps_lock_button, caps_on, "Caps Lock")
            self._set_lock_button_state(self.num_lock_button, num_on, "Num Lock")
            if self._caps_lock_on is not None and caps_on != self._caps_lock_on:
                self._send_lock_notification("Caps Lock", caps_on, 12345)
            if self._num_lock_on is not None and num_on != self._num_lock_on:
                self._send_lock_notification("Num Lock", num_on, 12346)
        self._caps_lock_on = caps_on
        self._num_lock_on = num_on

        battery_present = bool(payload.get("battery_present", False))
        if not battery_present:
            self.battery_icon.hide()
            self.battery_value.hide()
            return
        capacity = int(payload.get("battery_capacity", 0) or 0)
        status = str(payload.get("battery_status", "")).strip()
        if status == "Charging":
            icon = "battery_charging_full"
        elif capacity >= 90:
            icon = "battery_full"
        elif capacity >= 65:
            icon = "battery_5_bar"
        elif capacity >= 40:
            icon = "battery_3_bar"
        elif capacity >= 20:
            icon = "battery_2_bar"
        else:
            icon = "battery_alert"
        self._apply_icon_to_widget(self.battery_icon, icon, material_icon(icon), 16)
        self.battery_value.setText(str(capacity))
        self.battery_icon.show()
        self.battery_value.show()

    def _finish_system_state_worker(self) -> None:
        self._system_state_worker = None

    def _poll_updates_count(self) -> None:
        if self._updates_worker is not None and self._updates_worker.isRunning():
            return
        self._updates_worker = UpdateCountWorker()
        self._updates_worker.loaded.connect(self._apply_updates_count_payload)
        self._updates_worker.finished.connect(self._finish_updates_worker)
        self._updates_worker.start()

    def _apply_updates_count_payload(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        system_updates = [
            str(item) for item in payload.get("system_updates", []) if str(item).strip()
        ]
        flatpak_updates = [
            str(item)
            for item in payload.get("flatpak_updates", [])
            if str(item).strip()
        ]
        self._pending_updates_total = len(system_updates) + len(flatpak_updates)
        self._sync_updates_pill()

    def _finish_updates_worker(self) -> None:
        self._updates_worker = None

    def _poll_health_snapshot(self) -> None:
        if self._health_worker is not None and self._health_worker.isRunning():
            return
        service = load_health_service_settings()
        enabled = bool(service.get("enabled", False))
        show_in_bar = bool(service.get("show_in_bar", True))
        self.health_pill.setVisible(enabled and show_in_bar)
        if not enabled:
            return
        self._health_worker = HealthSnapshotWorker()
        self._health_worker.loaded.connect(self._apply_health_snapshot)
        self._health_worker.finished.connect(self._finish_health_worker)
        self._health_worker.start()

    def _apply_health_snapshot(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        self._health_snapshot = payload
        self._sync_health_pill()

    def _finish_health_worker(self) -> None:
        self._health_worker = None

    def _sync_updates_pill(self) -> None:
        total = max(0, int(self._pending_updates_total))
        self.updates_pill_count.setText("99+" if total > 99 else str(total))
        tooltip = (
            "System is up to date." if total == 0 else f"{total} update(s) pending."
        )
        self.updates_pill.setToolTip(tooltip)
        self.updates_pill_icon.setToolTip(tooltip)
        self.updates_pill_count.setToolTip(tooltip)

    def _sync_health_pill(self) -> None:
        steps = int(self._health_snapshot.get("steps", 0) or 0)
        self.health_pill_value.setText(format_steps_short(steps))
        tooltip = (
            health_tooltip(self._health_snapshot)
            if self._health_snapshot
            else "Health tracking"
        )
        self.health_pill.setToolTip(tooltip)
        self.health_pill_icon.setToolTip(tooltip)
        self.health_pill_value.setToolTip(tooltip)

    def _sync_health_pill_visibility(self) -> None:
        service = load_health_service_settings()
        enabled = bool(service.get("enabled", False))
        show_in_bar = bool(service.get("show_in_bar", True))
        self.health_pill.setVisible(enabled and show_in_bar)

    def _poll_weather(self) -> None:
        if self._weather_worker is not None and self._weather_worker.isRunning():
            return
        if configured_city() is None:
            self._weather_forecast = None
            self._weather_alert_seen_keys.clear()
            self._sync_weather_visibility()
            return
        self._weather_worker = WeatherWorker()
        self._weather_worker.loaded.connect(self._apply_weather_forecast)
        self._weather_worker.finished.connect(self._finish_weather_worker)
        self._weather_worker.start()

    def _parse_hhmm_minutes(self, value: object, fallback: str) -> int:
        text = str(value or fallback).strip() or fallback
        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if not match:
            text = fallback
            match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if match is None:
            return 0
        try:
            hours = max(0, min(23, int(match.group(1))))
            minutes = max(0, min(59, int(match.group(2))))
        except Exception:
            return 0
        return (hours * 60) + minutes

    def _minute_in_window(self, minute_of_day: int, start: int, end: int) -> bool:
        if start == end:
            return True
        if start < end:
            return start <= minute_of_day < end
        return minute_of_day >= start or minute_of_day < end

    def _aqi_category(self, aqi: int) -> int:
        if aqi <= 50:
            return 0
        if aqi <= 100:
            return 1
        if aqi <= 150:
            return 2
        if aqi <= 200:
            return 3
        if aqi <= 300:
            return 4
        return 5

    def _weather_notification_settings(self) -> dict[str, object]:
        weather = self.runtime_settings.get("weather", {})
        weather = weather if isinstance(weather, dict) else {}
        try:
            lead_minutes = max(
                5, min(180, int(weather.get("notify_lead_minutes", 30) or 30))
            )
        except Exception:
            lead_minutes = 30
        morning_start = self._parse_hhmm_minutes(
            weather.get("commute_morning_start", "07:00"), "07:00"
        )
        morning_end = self._parse_hhmm_minutes(
            weather.get("commute_morning_end", "09:00"), "09:00"
        )
        evening_start = self._parse_hhmm_minutes(
            weather.get("commute_evening_start", "17:00"), "17:00"
        )
        evening_end = self._parse_hhmm_minutes(
            weather.get("commute_evening_end", "19:00"), "19:00"
        )
        return {
            "enabled": bool(weather.get("notify_climate_changes", True)),
            "rain": bool(weather.get("notify_rain_soon", True)),
            "sunset": bool(weather.get("notify_sunset_soon", True)),
            "temperature_drop": bool(weather.get("notify_temperature_drop_soon", True)),
            "temperature_rise": bool(weather.get("notify_temperature_rise_soon", True)),
            "freezing_tonight": bool(weather.get("notify_freezing_risk_tonight", True)),
            "high_uv": bool(weather.get("notify_high_uv_window", True)),
            "strong_wind": bool(weather.get("notify_strong_wind_incoming", True)),
            "thunderstorm": bool(weather.get("notify_thunderstorm_likelihood", True)),
            "snow_ice": bool(weather.get("notify_snow_ice_start", True)),
            "fog_visibility": bool(weather.get("notify_fog_low_visibility", True)),
            "air_quality": bool(weather.get("notify_air_quality_worsening", True)),
            "pollen_high": bool(weather.get("notify_pollen_high", True)),
            "commute_morning_rain": bool(weather.get("notify_morning_commute_rain", True)),
            "commute_evening_risk": bool(weather.get("notify_evening_commute_risk", True)),
            "feels_extreme": bool(weather.get("notify_feels_like_extreme", True)),
            "sunrise": bool(weather.get("notify_sunrise_soon", True)),
            "dry_window_ending": bool(weather.get("notify_dry_window_ending", True)),
            "lead_minutes": lead_minutes,
            "morning_start": morning_start,
            "morning_end": morning_end,
            "evening_start": evening_start,
            "evening_end": evening_end,
        }

    def _send_weather_alert_notification(
        self,
        summary: str,
        body: str,
        *,
        icon_name: str = "not-available",
        replace_id: int = 18700,
    ) -> None:
        icon_path = animated_icon_path(icon_name)
        command = [
            "notify-send",
            "-a",
            "Hanauta Weather",
            "-r",
            str(replace_id),
            "-i",
            str(icon_path),
            summary,
            body,
        ]
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _maybe_notify_weather_changes(self, forecast: WeatherForecast) -> None:
        if len(self._weather_alert_seen_keys) > 256:
            self._weather_alert_seen_keys.clear()
        cfg = self._weather_notification_settings()
        if not bool(cfg.get("enabled", True)):
            return
        lead_minutes = int(cfg.get("lead_minutes", 30) or 30)
        city_label = forecast.city.label
        observed = None
        try:
            observed = datetime.fromisoformat(forecast.current.observed_time_iso)
        except Exception:
            observed = None
        if observed is None:
            observed = datetime.now()

        future_hours = [
            hour
            for hour in forecast.hourly
            if int(hour.minutes_from_current) >= 0 and int(hour.minutes_from_current) <= 24 * 60
        ]

        def _rain_like(hour: object) -> bool:
            try:
                return bool(hour.precipitation >= 0.1) or bool(hour.precipitation_probability >= 55)
            except Exception:
                return False

        def _notify_once(
            event_key: str,
            summary: str,
            body: str,
            *,
            icon_name: str,
            replace_id: int,
        ) -> None:
            if event_key in self._weather_alert_seen_keys:
                return
            self._send_weather_alert_notification(
                summary,
                body,
                icon_name=icon_name,
                replace_id=replace_id,
            )
            self._weather_alert_seen_keys.add(event_key)

        def _first_hour(predicate, max_minutes: int) -> object | None:
            for hour in future_hours:
                minutes = int(hour.minutes_from_current)
                if minutes > max_minutes:
                    continue
                if predicate(hour):
                    return hour
            return None

        if bool(cfg.get("rain", True)):
            hour = _first_hour(_rain_like, lead_minutes)
            if hour is not None:
                event_key = f"rain:{city_label}:{hour.time_iso}"
                minutes = int(hour.minutes_from_current)
                eta = "soon" if minutes <= 1 else f"in about {minutes} minutes"
                summary = f"Rain expected {eta}"
                body = (
                    f"{city_label}\n"
                    f"Chance: {hour.precipitation_probability}% • "
                    f"Forecast: {weather_condition_label(hour.weather_code)}"
                )
                _notify_once(
                    event_key,
                    summary,
                    body,
                    icon_name=hour.icon_name or "overcast-rain",
                    replace_id=18701,
                )

        if bool(cfg.get("sunset", True)):
            sunset_iso = str(forecast.current.sunset_iso).strip()
            if sunset_iso:
                try:
                    sunset = datetime.fromisoformat(sunset_iso)
                except Exception:
                    sunset = None
                if sunset is not None:
                    now_like = observed
                    minutes_left = int((sunset - now_like).total_seconds() // 60)
                    if 0 <= minutes_left <= lead_minutes:
                        sunset_key = f"sunset:{city_label}:{sunset.date().isoformat()}"
                        eta = (
                            "now"
                            if minutes_left <= 1
                            else f"in about {minutes_left} minutes"
                        )
                        _notify_once(
                            sunset_key,
                            f"Sunset {eta}",
                            f"{city_label}\nSunset at {forecast.current.sunset}",
                            icon_name="sunset",
                            replace_id=18702,
                        )

        if bool(cfg.get("temperature_drop", True)):
            hour = _first_hour(
                lambda item: item.temperature <= (forecast.current.temperature - 5.0),
                120,
            )
            if hour is not None:
                _notify_once(
                    f"temp-drop:{city_label}:{hour.time_iso}",
                    "Temperature drop soon",
                    f"{city_label}\nExpected {hour.temperature:.0f}° in about {int(hour.minutes_from_current)} minutes.",
                    icon_name=hour.icon_name or "overcast",
                    replace_id=18703,
                )

        if bool(cfg.get("temperature_rise", True)):
            hour = _first_hour(
                lambda item: item.temperature >= (forecast.current.temperature + 5.0),
                120,
            )
            if hour is not None:
                _notify_once(
                    f"temp-rise:{city_label}:{hour.time_iso}",
                    "Rapid heat rise",
                    f"{city_label}\nExpected {hour.temperature:.0f}° in about {int(hour.minutes_from_current)} minutes.",
                    icon_name=hour.icon_name or "clear-day",
                    replace_id=18704,
                )

        if bool(cfg.get("freezing_tonight", True)):
            hour = _first_hour(lambda item: item.temperature <= 0.0, 12 * 60)
            if hour is not None:
                _notify_once(
                    f"freeze:{city_label}:{observed.date().isoformat()}",
                    "Freezing risk tonight",
                    f"{city_label}\nForecast low around {hour.temperature:.0f}°.",
                    icon_name="overcast-snow",
                    replace_id=18705,
                )

        if bool(cfg.get("high_uv", True)):
            hour = _first_hour(lambda item: item.uv_index >= 6.0, 6 * 60)
            if hour is not None:
                _notify_once(
                    f"uv:{city_label}:{hour.time_iso}",
                    "High UV window",
                    f"{city_label}\nUV index may reach {hour.uv_index:.1f} soon.",
                    icon_name="clear-day",
                    replace_id=18706,
                )

        if bool(cfg.get("strong_wind", True)):
            hour = _first_hour(lambda item: item.wind_gusts >= 45.0, 6 * 60)
            if hour is not None:
                _notify_once(
                    f"wind:{city_label}:{hour.time_iso}",
                    "Strong wind incoming",
                    f"{city_label}\nGusts may reach {hour.wind_gusts:.0f} km/h.",
                    icon_name="overcast",
                    replace_id=18707,
                )

        if bool(cfg.get("thunderstorm", True)):
            hour = _first_hour(lambda item: int(item.weather_code) in {95, 96, 99}, 6 * 60)
            if hour is not None:
                _notify_once(
                    f"thunder:{city_label}:{hour.time_iso}",
                    "Thunderstorm likelihood",
                    f"{city_label}\nStorm conditions possible in about {int(hour.minutes_from_current)} minutes.",
                    icon_name="thunderstorms",
                    replace_id=18708,
                )

        if bool(cfg.get("snow_ice", True)):
            snow_codes = {56, 57, 66, 67, 71, 73, 75, 77, 85, 86}
            hour = _first_hour(
                lambda item: int(item.weather_code) in snow_codes
                or item.snowfall >= 0.1
                or (item.rain >= 0.2 and item.temperature <= 1.0),
                lead_minutes,
            )
            if hour is not None:
                _notify_once(
                    f"snow-ice:{city_label}:{hour.time_iso}",
                    "Snow or ice start soon",
                    f"{city_label}\n{weather_condition_label(hour.weather_code)} expected soon.",
                    icon_name="overcast-snow",
                    replace_id=18709,
                )

        if bool(cfg.get("fog_visibility", True)):
            hour = _first_hour(
                lambda item: int(item.weather_code) in {45, 48}
                or (item.visibility > 0 and item.visibility <= 1000.0),
                6 * 60,
            )
            if hour is not None:
                _notify_once(
                    f"fog:{city_label}:{hour.time_iso}",
                    "Fog / low visibility risk",
                    f"{city_label}\nVisibility may drop significantly soon.",
                    icon_name="fog",
                    replace_id=18710,
                )

        if bool(cfg.get("air_quality", True)):
            current_aqi = None
            if future_hours:
                current_aqi = future_hours[0].us_aqi
            worse_hour = None
            if current_aqi is not None:
                current_cat = self._aqi_category(int(current_aqi))
                for hour in future_hours:
                    if int(hour.minutes_from_current) > 6 * 60:
                        continue
                    if hour.us_aqi is None:
                        continue
                    if self._aqi_category(int(hour.us_aqi)) > current_cat:
                        worse_hour = hour
                        break
            if worse_hour is not None:
                _notify_once(
                    f"aqi:{city_label}:{worse_hour.time_iso}",
                    "Air quality worsening",
                    f"{city_label}\nAQI may rise to {int(worse_hour.us_aqi or 0)}.",
                    icon_name="overcast",
                    replace_id=18711,
                )

        if bool(cfg.get("pollen_high", True)):
            hour = _first_hour(
                lambda item: (item.pollen_index is not None and float(item.pollen_index) >= 80.0),
                12 * 60,
            )
            if hour is not None:
                _notify_once(
                    f"pollen:{city_label}:{hour.time_iso}",
                    "Pollen high alert",
                    f"{city_label}\nPollen levels may be high soon.",
                    icon_name="partly-cloudy-day",
                    replace_id=18712,
                )

        morning_start = int(cfg.get("morning_start", 7 * 60) or 7 * 60)
        morning_end = int(cfg.get("morning_end", 9 * 60) or 9 * 60)
        if bool(cfg.get("commute_morning_rain", True)):
            morning_hour = None
            for hour in future_hours:
                if int(hour.minutes_from_current) > 24 * 60:
                    continue
                try:
                    ts = datetime.fromisoformat(hour.time_iso)
                except Exception:
                    continue
                minute_of_day = (ts.hour * 60) + ts.minute
                if not self._minute_in_window(minute_of_day, morning_start, morning_end):
                    continue
                if _rain_like(hour):
                    morning_hour = hour
                    break
            if morning_hour is not None:
                _notify_once(
                    f"commute-am:{city_label}:{datetime.fromisoformat(morning_hour.time_iso).date().isoformat()}",
                    "Morning commute rain",
                    f"{city_label}\nRain risk during your morning commute window.",
                    icon_name=morning_hour.icon_name or "overcast-rain",
                    replace_id=18713,
                )

        evening_start = int(cfg.get("evening_start", 17 * 60) or 17 * 60)
        evening_end = int(cfg.get("evening_end", 19 * 60) or 19 * 60)
        if bool(cfg.get("commute_evening_risk", True)):
            evening_hour = None
            for hour in future_hours:
                if int(hour.minutes_from_current) > 24 * 60:
                    continue
                try:
                    ts = datetime.fromisoformat(hour.time_iso)
                except Exception:
                    continue
                minute_of_day = (ts.hour * 60) + ts.minute
                if not self._minute_in_window(minute_of_day, evening_start, evening_end):
                    continue
                if _rain_like(hour) or hour.snowfall >= 0.1 or hour.wind_gusts >= 40.0:
                    evening_hour = hour
                    break
            if evening_hour is not None:
                _notify_once(
                    f"commute-pm:{city_label}:{datetime.fromisoformat(evening_hour.time_iso).date().isoformat()}",
                    "Evening commute weather risk",
                    f"{city_label}\nRain, snow, or strong wind risk in evening commute.",
                    icon_name=evening_hour.icon_name or "overcast",
                    replace_id=18714,
                )

        if bool(cfg.get("feels_extreme", True)):
            hour = _first_hour(
                lambda item: item.apparent_temperature <= -5.0
                or item.apparent_temperature >= 35.0,
                6 * 60,
            )
            if hour is not None:
                _notify_once(
                    f"feels:{city_label}:{hour.time_iso}",
                    "Feels-like extreme",
                    f"{city_label}\nFeels like {hour.apparent_temperature:.0f}° soon.",
                    icon_name=hour.icon_name or "not-available",
                    replace_id=18715,
                )

        if bool(cfg.get("sunrise", True)):
            sunrise_iso = str(forecast.current.sunrise_iso).strip()
            if sunrise_iso:
                try:
                    sunrise = datetime.fromisoformat(sunrise_iso)
                except Exception:
                    sunrise = None
                if sunrise is not None:
                    minutes_left = int((sunrise - observed).total_seconds() // 60)
                    if 0 <= minutes_left <= lead_minutes:
                        _notify_once(
                            f"sunrise:{city_label}:{sunrise.date().isoformat()}",
                            "Sunrise soon",
                            f"{city_label}\nSunrise at {forecast.current.sunrise}.",
                            icon_name="sunrise",
                            replace_id=18716,
                        )

        if bool(cfg.get("dry_window_ending", True)):
            current_dry = (
                forecast.current.precipitation < 0.05
                and forecast.current.weather_code not in {61, 63, 65, 80, 81, 82}
            )
            if current_dry:
                hour = _first_hour(_rain_like, lead_minutes)
                if hour is not None and int(hour.minutes_from_current) >= 15:
                    _notify_once(
                        f"dry-ending:{city_label}:{hour.time_iso}",
                        "Dry window ending",
                        f"{city_label}\nPrecipitation may begin in about {int(hour.minutes_from_current)} minutes.",
                        icon_name=hour.icon_name or "overcast-rain",
                        replace_id=18717,
                    )

    def _apply_weather_forecast(self, forecast: object) -> None:
        self._weather_forecast = (
            forecast if isinstance(forecast, WeatherForecast) else None
        )
        if self._weather_forecast is not None:
            current = self._weather_forecast.current
            self.weather_icon.set_icon_path(animated_icon_path(current.icon_name))
            self.weather_icon.setToolTip(
                f"{self._weather_forecast.city.label} • {round(current.temperature):.0f}° • {current.condition}"
            )
            self._maybe_notify_weather_changes(self._weather_forecast)
        self._sync_weather_visibility()

    def _finish_weather_worker(self) -> None:
        self._weather_worker = None

    def _cap_alerts_service_visible(self) -> bool:
        services = load_service_settings()
        service = services.get("cap_alerts", {})
        if not isinstance(service, dict):
            service = {}
        return bool(service.get("enabled", True)) and bool(
            service.get("show_in_bar", True)
        )

    def _poll_cap_alerts(self) -> None:
        if not self._cap_alerts_service_visible():
            self._cap_alerts = []
            self._cap_alert_seen_ids.clear()
            self._sync_cap_alert_chip()
            return
        if configured_alert_location() is None and not test_mode_enabled():
            self._cap_alerts = []
            self._cap_alert_seen_ids.clear()
            self._sync_cap_alert_chip()
            return
        if self._cap_alert_worker is not None and self._cap_alert_worker.isRunning():
            return
        self._cap_alert_worker = CapAlertWorker()
        self._cap_alert_worker.loaded.connect(self._apply_cap_alerts)
        self._cap_alert_worker.finished.connect(self._finish_cap_alert_worker)
        self._cap_alert_worker.start()

    def _apply_cap_alerts(self, alerts_obj: object) -> None:
        alerts = list(alerts_obj) if isinstance(alerts_obj, list) else []
        active_ids = {
            alert.identifier for alert in alerts if isinstance(alert, CapAlert)
        }
        new_ids = active_ids - self._cap_alert_seen_ids
        self._cap_alerts = alerts
        if active_ids:
            self._cap_alert_seen_ids = active_ids
        else:
            self._cap_alert_seen_ids.clear()
        if new_ids:
            top = top_alert(self._cap_alerts)
            if top is not None:
                self._play_cap_alert_sound()
                self._show_cap_alert_overlay(top)
        self._sync_cap_alert_chip()

    def _finish_cap_alert_worker(self) -> None:
        self._cap_alert_worker = None

    def _sync_cap_alert_chip(self) -> None:
        visible = self._cap_alerts_service_visible()
        alert = top_alert(self._cap_alerts) if visible else None
        if alert is None:
            self._cap_alert_accent = "#FBC02D"
            self.cap_alert_chip.hide()
            self.cap_alert_glow_frame.hide()
            self.cap_alert_chip.setToolTip("")
            return
        self._cap_alert_accent = alert_accent_color(alert)
        self._apply_cap_alert_chip_style(self._cap_alert_accent)
        summary = f"{alert.event} • {relative_expiry(alert)}".strip(" •")
        if len(self._cap_alerts) > 1:
            summary = f"{len(self._cap_alerts)} alerts • {alert.event}"
        self.cap_alert_icon.set_icon_path(animated_icon_path(alert.icon_name))
        if test_mode_enabled():
            self.cap_alert_text.setText(f"Demo • {summary or alert.event}")
        else:
            self.cap_alert_text.setText(summary or alert.event)
        location = configured_alert_location()
        tooltip_parts = [
            alert.headline or alert.event,
            alert.area_desc or "",
            f"Source: {alert.sender_name}",
        ]
        if test_mode_enabled():
            tooltip_parts.append(
                "Demo mode is enabled. These are sample alerts for UI testing."
            )
        if location is not None:
            tooltip_parts.append(f"Location: {location.label}")
        self.cap_alert_chip.setToolTip(
            "\n".join(part for part in tooltip_parts if part)
        )
        self.cap_alert_glow_frame.setGeometry(self.cap_alert_chip.rect())
        self.cap_alert_glow_frame.show()
        self.cap_alert_chip.show()

    def _apply_cap_alert_chip_style(self, accent: str) -> None:
        text_color = "#101114" if QColor(accent).lightnessF() > 0.62 else "#FFF9E8"
        warning_color = accent if QColor(accent).lightnessF() <= 0.82 else "#C99200"
        self.cap_alert_chip.setStyleSheet(
            f"""
            QFrame#capAlertChip {{
                background: {rgba(accent, 0.30)};
                border: 1px solid {rgba(accent, 0.58)};
            }}
            QFrame#capAlertChip:hover {{
                background: {rgba(accent, 0.38)};
                border: 1px solid {rgba(accent, 0.76)};
            }}
            """
        )
        self.cap_alert_warning.setStyleSheet(
            f'color: {warning_color}; font-family: "{self.material_font}"; font-size: 17px;'
        )
        self.cap_alert_text.setStyleSheet(
            f"color: {text_color}; font-size: 11px; font-weight: 700;"
        )

    def _tick_cap_alert_pulse(self) -> None:
        if not self.cap_alert_chip.isVisible():
            self.cap_alert_glow_frame.hide()
            self.cap_alert_warning_opacity.setOpacity(1.0)
            return
        self._cap_alert_pulse_tick = (self._cap_alert_pulse_tick + 1) % 360
        phase = self._cap_alert_pulse_tick / 18.0
        alpha = 0.20 + (0.30 * ((math.sin(phase) + 1.0) / 2.0))
        width = 2 if math.sin(phase * 1.2) < 0.35 else 3
        # Fast fade in/out using only opacity (no size/layout changes).
        icon_phase = self._cap_alert_pulse_tick / 6.0
        icon_alpha = 0.20 + (0.80 * ((math.sin(icon_phase) + 1.0) / 2.0))
        self.cap_alert_warning_opacity.setOpacity(icon_alpha)
        self.cap_alert_glow_frame.setStyleSheet(
            f"background: transparent; border: {width}px solid {rgba(self._cap_alert_accent, alpha)}; border-radius: 14px;"
        )
        self.cap_alert_glow_frame.setGeometry(self.cap_alert_chip.rect())
        self.cap_alert_glow_frame.show()

    def _play_cap_alert_sound(self) -> None:
        sound_path = Path("/usr/share/sounds/freedesktop/stereo/complete.ogg")
        if sound_path.exists() and shutil.which("paplay"):
            try:
                subprocess.Popen(
                    ["paplay", "--volume=18000", str(sound_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass

    def _show_cap_alert_overlay(self, alert: CapAlert) -> None:
        if CAP_ALERTS_OVERLAY is None or not CAP_ALERTS_OVERLAY.exists():
            return
        if self._singleton_active(self._cap_alert_overlay_process, CAP_ALERTS_OVERLAY):
            self._terminate_singleton_process(
                "_cap_alert_overlay_process", CAP_ALERTS_OVERLAY
            )
        command = entry_command(
            CAP_ALERTS_OVERLAY,
            "--title",
            alert.event,
            "--headline",
            alert.headline or alert.event,
            "--area",
            alert.area_desc or "",
            "--tip",
            alert.instruction or fallback_tip(alert),
            "--contact",
            alert.contact_number or "",
            "--url",
            alert.web or "",
            "--icon",
            alert.icon_name,
            "--severity",
            alert.severity,
            "--alert-color",
            alert.color,
        )
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
            return

    def _send_action_notification(
        self,
        summary: str,
        body: str,
        action_label: str,
        open_url: str,
        replace_id: int,
    ) -> None:
        if not action_notifications_supported() or not open_url.strip():
            try:
                subprocess.Popen(
                    ["notify-send", "-a", "Hanauta RSS", summary, body],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass
            return
        run_bg(
            entry_command(
                ACTION_NOTIFICATION_SCRIPT,
                "--app-name",
                "Hanauta RSS",
                "--summary",
                summary,
                "--body",
                body,
                "--action-label",
                action_label,
                "--open-url",
                open_url,
                "--replace-id",
                str(replace_id),
            )
        )

    def _poll_rss_notifications(self) -> None:
        settings = load_runtime_settings()
        services = settings.get("services", {})
        rss_settings = settings.get("rss", {})
        if not isinstance(services, dict) or not isinstance(rss_settings, dict):
            return
        service = services.get("rss_widget", {})
        if not isinstance(service, dict) or not bool(service.get("enabled", True)):
            return
        if not bool(rss_settings.get("notify_new_items", True)):
            return
        cache = load_rss_cache()
        interval = max(5, int(rss_settings.get("check_interval_minutes", 15) or 15))
        checked = cache.get("last_checked_at", "")
        if checked and not crypto_should_check(str(checked), interval):
            return
        try:
            _sources, entries = collect_rss_entries(settings)
        except Exception:
            return
        seen = set(str(item) for item in cache.get("seen", []))
        if not seen:
            cache["seen"] = [rss_entry_fingerprint(item) for item in entries]
            cache["last_checked_at"] = datetime.now().astimezone().isoformat()
            save_rss_cache(cache)
            return
        new_items: list[dict[str, str]] = []
        for item in entries:
            fingerprint = rss_entry_fingerprint(item)
            if fingerprint not in seen:
                new_items.append(item)
            seen.add(fingerprint)
        cache["seen"] = list(seen)
        cache["last_checked_at"] = datetime.now().astimezone().isoformat()
        save_rss_cache(cache)
        if new_items and bool(rss_settings.get("play_notification_sound", False)):
            sound_path = Path("/usr/share/sounds/freedesktop/stereo/complete.ogg")
            if sound_path.exists() and shutil.which("paplay"):
                try:
                    subprocess.Popen(
                        ["paplay", str(sound_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except Exception:
                    pass
        for index, item in enumerate(new_items[:3]):
            title = str(item.get("title", "New story")).strip() or "New story"
            feed_title = str(item.get("feed_title", "")).strip() or "RSS feed"
            detail = str(item.get("detail", "")).strip() or feed_title
            link = str(item.get("link", "")).strip()
            if not link:
                continue
            body = f"{feed_title}\n{detail[:150]}"
            self._send_action_notification(title, body, "Read", link, 22000 + index)

    def _poll_crypto_notifications(self) -> None:
        # Crypto alerts now come from the dedicated notifier daemon so they still
        # fire when the widget is closed and without depending on the bar process.
        return

    def _poll_mail_state(self) -> None:
        service = self.service_settings.get("mail", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        worker_running = bool(
            self._mail_worker is not None and self._mail_worker.isRunning()
        )
        logger.debug(
            "Mail poll triggered enabled=%s worker_running=%s", enabled, worker_running
        )
        if not enabled:
            self._mail_account_summary = []
            self._mail_unread_total = 0
            self._sync_mail_button_visibility()
            return
        if worker_running:
            logger.debug("Mail worker already running; skipping new poll")
            return
        due_account_ids: set[int] = set()
        try:
            conn = sqlite3.connect(mail_db_path())
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, poll_interval_seconds FROM accounts"
            ).fetchall()
        except Exception:
            rows = []
        finally:
            try:
                conn.close()  # type: ignore[name-defined]
            except Exception:
                pass
        now_ts = datetime.now().timestamp()
        for row in rows:
            account_id = int(row["id"])
            interval = max(30, int(row["poll_interval_seconds"] or 90))
            last_sync = float(self._mail_last_sync_at.get(account_id, 0.0))
            if last_sync <= 0 or (now_ts - last_sync) >= interval:
                due_account_ids.add(account_id)
        logger.debug("Mail poll due accounts=%s", sorted(due_account_ids))
        self._mail_worker = MailPollWorker(
            due_account_ids, mail_settings_from_payload(self.runtime_settings), self
        )
        self._mail_worker.loaded.connect(self._apply_mail_state)
        self._mail_worker.finished.connect(self._finish_mail_worker)
        self._mail_worker.start()
        logger.debug("Mail worker started for accounts=%s", sorted(due_account_ids))

    def _apply_mail_state(self, payload_obj: object) -> None:
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        self._mail_account_summary = (
            list(payload.get("accounts", []))
            if isinstance(payload.get("accounts", []), list)
            else []
        )
        self._mail_unread_total = max(0, int(payload.get("total_unread", 0) or 0))
        for account_id in (
            payload.get("synced_account_ids", [])
            if isinstance(payload.get("synced_account_ids", []), list)
            else []
        ):
            self._mail_last_sync_at[int(account_id)] = datetime.now().timestamp()
        notifications = payload.get("notifications", [])
        logger.debug(
            "Mail state payload notifications=%d total_unread=%d",
            len(notifications) if isinstance(notifications, list) else 0,
            self._mail_unread_total,
        )
        logger.debug(
            "Mail account summary=%d accounts notification sound=%s",
            len(self._mail_account_summary),
            bool(
                mail_settings_from_payload(self.runtime_settings).get(
                    "play_notification_sound", False
                )
            ),
        )
        if isinstance(notifications, list):
            for item in notifications:
                if isinstance(item, dict):
                    self._send_mail_notification(item)
            if notifications and mail_settings_from_payload(self.runtime_settings).get(
                "play_notification_sound", False
            ):
                self._play_mail_notification_sound()
        if not notifications:
            logger.debug("Mail poll produced no notification payload")
        self._sync_mail_button_visibility()

    def _finish_mail_worker(self) -> None:
        self._mail_worker = None

    def _mail_button_tooltip(self) -> str:
        if not self._mail_account_summary:
            return "Mail"
        lines = [f"Unread mail: {self._mail_unread_total}"]
        for account in self._mail_account_summary:
            if not isinstance(account, dict):
                continue
            label = (
                str(account.get("display_name", "")).strip()
                or str(account.get("label", "")).strip()
                or str(account.get("email_address", "")).strip()
                or "Mailbox"
            )
            lines.append(f"{label}: {int(account.get('unread_count', 0) or 0)}")
        return "\n".join(lines)

    @pyqtSlot(int, str)
    def _handle_mail_notification_action(
        self, notification_id: int, action_key: str
    ) -> None:
        if action_key != MAIL_NOTIFICATION_ACTION_KEY:
            return
        command = self._mail_notification_actions.pop(int(notification_id), None)
        if command:
            run_bg_detached(command)

    @pyqtSlot(int, int)
    def _handle_mail_notification_closed(
        self, notification_id: int, reason: int
    ) -> None:
        self._mail_notification_actions.pop(int(notification_id), None)

    def _sync_mail_button_visibility(self) -> None:
        service = load_service_settings().get("mail", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        has_accounts = bool(self._mail_account_summary)
        visible = enabled and has_accounts
        logger.debug(
            "Sync mail visibility enabled=%s has_accounts=%s unread=%d visible=%s",
            enabled,
            has_accounts,
            self._mail_unread_total,
            visible,
        )
        self.mail_wrap.setVisible(visible)
        self.mail_count.setText(
            "99+" if self._mail_unread_total > 99 else str(self._mail_unread_total)
        )
        tooltip = self._mail_button_tooltip()
        self.mail_wrap.setToolTip(tooltip)
        self.mail_button.setToolTip(tooltip)
        self.mail_count.setToolTip(tooltip)

    def _open_mail_client(self) -> None:
        if EMAIL_CLIENT is None or not EMAIL_CLIENT.exists():
            return
        command = entry_command(EMAIL_CLIENT)
        if not command:
            return
        run_bg_detached(command)

    def _show_mail_notification_with_action(
        self, summary: str, body: str, command: list[str], replace_id: int
    ) -> bool:
        interface = self._mail_notification_interface
        if interface is None:
            logger.debug(
                "Mail notification interface is unavailable; falling back to notify-send"
            )
            return False
        try:
            response = interface.call(
                "Notify",
                "Hanauta Mail",
                replace_id,
                "",
                summary,
                body,
                [MAIL_NOTIFICATION_ACTION_KEY, "Read"],
                {"x-canonical-private-synchronous": f"hanauta-mail-{replace_id}"},
                MAIL_NOTIFICATION_TIMEOUT_MS,
            )
        except Exception as exc:
            logger.debug("Mail notification bus call failed: %s", exc)
            return False
        if response.type() == QDBusMessage.MessageType.ErrorMessage:
            logger.debug(
                "Mail notification bus call error: %s", response.errorMessage()
            )
            return False
        args = response.arguments()
        if not args:
            return False
        try:
            notification_id = int(args[0])
        except Exception:
            return False
        if notification_id <= 0:
            return False
        self._mail_notification_actions[notification_id] = list(command)
        logger.debug(
            "Mail notification registered id=%d command=%s", notification_id, command
        )
        return True

    def _send_mail_notification(self, item: dict[str, object]) -> None:
        logger.info("Dispatching mail notification for %s", item.get("account_label"))
        mail_settings = mail_settings_from_payload(self.runtime_settings)
        account_label = str(item.get("account_label", "")).strip() or "Mailbox"
        message_key = str(item.get("message_key", "")).strip()
        if not message_key:
            return
        if mail_settings.get("hide_notification_content", False):
            summary = f"{account_label}: New email message received"
            body = ""
        else:
            subject = truncate_mail_text(
                str(item.get("subject", "")).strip() or "(No subject)", 56
            )
            detail = truncate_mail_text(str(item.get("snippet", "")).strip(), 120)
            summary = f"{account_label}: {subject}"
            body = detail
        logger.debug(
            "Prepared mail notification summary=%s body_length=%d hide_content=%s",
            summary,
            len(body),
            mail_settings.get("hide_notification_content", False),
        )
        command = entry_command(OPEN_MAIL_MESSAGE, "--message-key", message_key)
        replace_id = 26000 + abs(hash(message_key)) % 1000
        logger.debug("Mail notification command=%s replace_id=%d", command, replace_id)
        if command and self._show_mail_notification_with_action(
            summary, body, command, replace_id
        ):
            return
        logger.debug(
            "Action notification failed, falling back to notify-send for %s", summary
        )
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Hanauta Mail", summary, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            logger.exception("Failed to show mail notification: %s", exc)

    def _play_mail_notification_sound(self) -> None:
        sound_path = preferred_mail_sound_path()
        if sound_path is None or not shutil.which("paplay"):
            return
        try:
            subprocess.Popen(
                ["paplay", "--volume=15000", str(sound_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _sync_weather_visibility(self) -> None:
        settings = load_runtime_settings()
        weather = settings.get("weather", {})
        if not isinstance(weather, dict):
            weather = {}
        enabled = bool(weather.get("enabled", False))
        valid_city = bool(str(weather.get("name", "")).strip())
        self.weather_icon.setVisible(enabled and valid_city)

    def _poll_network(self) -> None:
        connected = run_script("network.sh", "status") == "Connected"
        self._apply_icon_to_widget(
            self.net_icon,
            "wifi" if connected else "wifi_off",
            material_icon("wifi" if connected else "wifi_off"),
            16,
        )
        vpn_payload = {}
        parsed_status = False
        raw = run_script("vpn.sh", "--status")
        if raw:
            try:
                vpn_payload = json.loads(raw)
                parsed_status = True
            except Exception:
                vpn_payload = {}
        wireguard_state = str(vpn_payload.get("wireguard", "")).strip().lower()
        wg_active = wireguard_state == "on"
        wg_inactive = wireguard_state == "off"
        selected_iface = str(vpn_payload.get("wg_selected", "")).strip()
        wg_alert = (
            (not raw.strip())
            or (raw.strip() and not parsed_status)
            or (parsed_status and not (wg_active or wg_inactive))
            or (parsed_status and not selected_iface)
        )
        self._set_vpn_button_icon(wg_active, alert=wg_alert)
        self.vpn_icon.setProperty("active", wg_active)
        self.vpn_icon.setProperty("alert", wg_alert)
        self.vpn_icon.setToolTip(f"WireGuard: {selected_iface or 'No config selected'}")
        self.style().unpolish(self.vpn_icon)
        self.style().polish(self.vpn_icon)

    def _widget_icon_tint_color(self) -> QColor:
        return QColor(self.theme.primary)

    def _widget_icon(self, path: Path, size: int, *, prefer_color: bool) -> QIcon:
        if not path.exists():
            return QIcon()
        if prefer_color:
            icon = native_svg_icon(path, size)
            if icon.isNull():
                return QIcon(str(path))
            return icon
        suffix = path.suffix.lower()
        if suffix == ".svg":
            icon = tinted_svg_icon(path, self._widget_icon_tint_color(), size)
            if not icon.isNull():
                return icon
            return native_svg_icon(path, size)
        icon = tinted_raster_icon(path, self._widget_icon_tint_color(), size)
        if not icon.isNull():
            return icon
        return QIcon(str(path))

    def _set_vpn_button_icon(self, active: bool, alert: bool | None = None) -> None:
        prefer_color = bool(self.bar_settings.get("use_color_widget_icons", False))
        if alert is None:
            alert = self.vpn_icon.property("alert") == True
        override_prop = (
            "pluginIconPathAlert"
            if alert
            else ("pluginIconPathActive" if active else "pluginIconPathInactive")
        )
        override_value = str(self.vpn_icon.property(override_prop) or "").strip()
        override_path = Path(override_value).expanduser() if override_value else None
        icon = QIcon()
        if override_path is not None and override_path.exists():
            icon = self._widget_icon(override_path, 16, prefer_color=prefer_color)
        if icon.isNull():
            icon_path = VPN_ICON_ON if active else VPN_ICON_OFF
            icon = self._widget_icon(icon_path, 16, prefer_color=prefer_color)
        # Keep iconKey valid for generic refreshers that may rebuild icon text.
        if alert:
            icon_key = "warning"
        else:
            icon_key = "vpn_key" if active else "shield"
        self.vpn_icon.setProperty("iconKey", icon_key)
        self.vpn_icon.setProperty("nerdIcon", False)
        self.vpn_icon.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.vpn_icon.setIcon(icon)
            self.vpn_icon.setIconSize(QSize(16, 16))
            self.vpn_icon.setText("")
            return
        self.vpn_icon.setIcon(QIcon())
        self.vpn_icon.setText(self._icon_text(icon_key))

    def _set_christian_button_icon(self) -> None:
        icon = self._widget_icon(
            CHRISTIAN_ICON,
            16,
            prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
        )
        if not icon.isNull():
            self.christian_button.setIcon(icon)
            self.christian_button.setIconSize(QSize(16, 16))
            self.christian_button.setText("")
            return
        self.christian_button.setIcon(QIcon())
        self.christian_button.setText(
            self._bar_icon_overrides.get(
                "christian_widget", material_icon("auto_awesome")
            )
        )
        self.christian_button.setFont(QFont(self.material_font, 16))

    def _set_reminders_button_icon(self) -> None:
        icon = self._widget_icon(
            REMINDER_ICON,
            20,
            prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
        )
        self.reminders_button.setProperty("iconKey", "reminder_widget")
        self.reminders_button.setProperty("nerdIcon", False)
        self.reminders_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.reminders_button.setIcon(icon)
            self.reminders_button.setIconSize(QSize(20, 20))
            self.reminders_button.setText("")
            return
        self.reminders_button.setIcon(QIcon())
        self.reminders_button.setText(REMINDERS_BAR_GLYPH)

    def _set_pomodoro_button_icon(self) -> None:
        icon = self._widget_icon(
            POMODORO_ICON,
            20,
            prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
        )
        self.pomodoro_button.setProperty("iconKey", "pomodoro_widget")
        self.pomodoro_button.setProperty("nerdIcon", False)
        self.pomodoro_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.pomodoro_button.setIcon(icon)
            self.pomodoro_button.setIconSize(QSize(20, 20))
            self.pomodoro_button.setText("")
            return
        self.pomodoro_button.setIcon(QIcon())
        self.pomodoro_button.setText(self._icon_text("timer"))

    def _set_rss_button_icon(self) -> None:
        prefer_color = bool(self.bar_settings.get("use_color_widget_icons", False))
        icon = self._widget_icon(
            resolve_rss_icon_path(prefer_color=prefer_color),
            16,
            prefer_color=prefer_color,
        )
        self.rss_button.setProperty("iconKey", "rss_feed")
        self.rss_button.setProperty("nerdIcon", False)
        self.rss_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.rss_button.setIcon(icon)
            self.rss_button.setIconSize(QSize(16, 16))
            self.rss_button.setText("")
            return
        self.rss_button.setIcon(QIcon())
        self.rss_button.setText(
            self._bar_icon_overrides.get("rss_feed", material_icon("public"))
        )

    def _set_ntfy_button_icon(self) -> None:
        prefer_color = bool(self.bar_settings.get("use_color_widget_icons", False))
        icon = self._widget_icon(
            resolve_ntfy_icon_path(prefer_color=prefer_color),
            16,
            prefer_color=prefer_color,
        )
        self.ntfy_button.setProperty("iconKey", "notifications")
        self.ntfy_button.setProperty("nerdIcon", False)
        self.ntfy_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.ntfy_button.setIcon(icon)
            self.ntfy_button.setIconSize(QSize(16, 16))
            self.ntfy_button.setText("")
            return
        self.ntfy_button.setIcon(QIcon())
        self.ntfy_button.setText(
            self._bar_icon_overrides.get(
                "notifications", material_icon("notifications")
            )
        )

    def _set_crypto_button_icon(self) -> None:
        icon = self._widget_icon(
            CRYPTO_ICON,
            20,
            prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
        )
        self.crypto_button.setProperty("iconKey", "show_chart")
        self.crypto_button.setProperty("nerdIcon", False)
        self.crypto_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.crypto_button.setIcon(icon)
            self.crypto_button.setIconSize(QSize(20, 20))
            self.crypto_button.setText("")
            return
        self.crypto_button.setIcon(QIcon())
        self.crypto_button.setText(
            self._bar_icon_overrides.get("show_chart", material_icon("md-bitcoin"))
        )

    def _set_game_mode_button_icon(self) -> None:
        prefer_color = bool(self.bar_settings.get("use_color_widget_icons", False))
        icon = self._widget_icon(
            resolve_game_mode_icon_path(prefer_color=prefer_color),
            20,
            prefer_color=prefer_color,
        )
        self.game_mode_button.setProperty("iconKey", "sports_esports")
        self.game_mode_button.setProperty("nerdIcon", False)
        self.game_mode_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.game_mode_button.setIcon(icon)
            self.game_mode_button.setIconSize(QSize(20, 20))
            self.game_mode_button.setText("")
            return
        self.game_mode_button.setIcon(QIcon())
        self.game_mode_button.setText(
            self._bar_icon_overrides.get(
                "sports_esports", material_icon("sports_esports")
            )
        )

    def _set_clipboard_button_icon(self) -> None:
        icon = self._widget_icon(
            CLIPBOARD_ICON,
            16,
            prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
        )
        self.btn_clip.setProperty("iconKey", "content_paste")
        self.btn_clip.setProperty("nerdIcon", False)
        self.btn_clip.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.btn_clip.setIcon(icon)
            self.btn_clip.setIconSize(QSize(16, 16))
            self.btn_clip.setText("")
            return
        self.btn_clip.setIcon(QIcon())
        self.btn_clip.setText(
            self._bar_icon_overrides.get(
                "content_paste", material_icon("content_paste")
            )
        )

    def _set_obs_button_icon(self) -> None:
        if self._obs_recording:
            icon_path = (
                OBS_RECORDING_ACTIVE_ICON
                if self._obs_flash_visible
                else OBS_RECORDING_INACTIVE_ICON
            )
            icon = self._widget_icon(
                icon_path,
                16,
                prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
            )
        elif self._obs_streaming:
            icon = self._widget_icon(
                OBS_STREAMING_ACTIVE_ICON,
                16,
                prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
            )
        else:
            icon = self._widget_icon(
                OBS_ICON,
                16,
                prefer_color=bool(self.bar_settings.get("use_color_widget_icons", False)),
            )
        self.obs_button.setProperty("iconKey", "videocam")
        self.obs_button.setProperty("nerdIcon", False)
        self.obs_button.setFont(QFont(self.material_font, 16))
        if not icon.isNull():
            self.obs_button.setIcon(icon)
            self.obs_button.setIconSize(QSize(12, 12))
            self.obs_button.setText("")
            return
        self.obs_button.setIcon(QIcon())
        self.obs_button.setText(
            self._bar_icon_overrides.get("videocam", material_icon("videocam"))
        )

    def _tick_obs_recording_flash(self) -> None:
        if not self._obs_recording:
            if not self._obs_flash_visible:
                self._obs_flash_visible = True
                self._set_obs_button_icon()
            return
        self._obs_flash_visible = not self._obs_flash_visible
        self._set_obs_button_icon()

    def _poll_obs_state(self) -> None:
        if OBS_STATUS is None or not OBS_STATUS.exists():
            return
        raw = run_cmd(entry_command(OBS_STATUS), timeout=4.0)
        if not raw:
            self._obs_streaming = False
            self._obs_recording = False
            self._obs_flash_visible = True
            self._set_obs_button_icon()
            return
        try:
            payload = json.loads(raw)
        except Exception:
            return
        self._obs_streaming = bool(payload.get("streaming", False))
        self._obs_recording = bool(payload.get("recording", False))
        if not self._obs_recording:
            self._obs_flash_visible = True
        self._set_obs_button_icon()

    def _sync_christian_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("christian_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(
            service.get(
                "show_in_bar", service.get("show_in_notification_center", False)
            )
        )
        self.christian_button.setVisible(enabled and show_in_bar)

    def _sync_reminders_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("reminders_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", False))
        show_in_bar = bool(service.get("show_in_bar", False))
        self.reminders_button.setVisible(enabled and show_in_bar)

    def _sync_pomodoro_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("pomodoro_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", False))
        self.pomodoro_button.setVisible(enabled and show_in_bar)

    def _sync_rss_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("rss_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", False))
        has_script = resolve_rss_widget_script().exists()
        self.rss_button.setVisible(enabled and show_in_bar and has_script)

    def _sync_obs_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("obs_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", False))
        self.obs_button.setVisible(enabled and show_in_bar)

    def _sync_crypto_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("crypto_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", False))
        self.crypto_button.setVisible(enabled and show_in_bar)

    def _sync_ntfy_button_visibility(self) -> None:
        ntfy = self.runtime_settings.get("ntfy", {})
        if not isinstance(ntfy, dict):
            ntfy = {}
        enabled = bool(ntfy.get("enabled", False))
        show_in_bar = bool(ntfy.get("show_in_bar", False))
        self.ntfy_button.setVisible(enabled and show_in_bar)

    def _sync_game_mode_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("game_mode", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", False))
        show_in_bar = bool(service.get("show_in_bar", False))
        self.game_mode_button.setVisible(enabled and show_in_bar)

    def _sync_desktop_clock_process(self, has_real_windows: bool | None = None) -> None:
        service = self.service_settings.get("desktop_clock_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        target = desktop_clock_target()
        if has_real_windows is None:
            has_real_windows = bool(
                getattr(self, "_focused_workspace_has_real_windows", False)
            )
        should_run = enabled and target is not None and not has_real_windows
        if not should_run:
            if DESKTOP_CLOCK_WIDGET:
                terminate_background_matches(str(DESKTOP_CLOCK_WIDGET))
            terminate_background_matches(str(DESKTOP_CLOCK_BINARY))
            if (
                self._desktop_clock_process is not None
                and self._desktop_clock_process.poll() is None
            ):
                self._desktop_clock_process.terminate()
            self._desktop_clock_process = None
            return
        if (
            self._desktop_clock_process is not None
            and self._desktop_clock_process.poll() is None
        ):
            return
        if DESKTOP_CLOCK_WIDGET:
            terminate_background_matches(str(DESKTOP_CLOCK_WIDGET))
        terminate_background_matches(str(DESKTOP_CLOCK_BINARY))
        command = desktop_clock_command()
        if not command:
            self._desktop_clock_process = None
            return
        try:
            self._desktop_clock_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            self._desktop_clock_process = None

    def _restart_desktop_clock_for_theme_change(self) -> None:
        if (
            self._desktop_clock_process is not None
            and self._desktop_clock_process.poll() is None
        ):
            self._desktop_clock_process.terminate()
            self._desktop_clock_process = None
        self._sync_desktop_clock_process()

    def _poll_lock_states(self) -> None:
        if self._lock_keys_plugin_owns_bar():
            self.caps_lock_button.hide()
            self.num_lock_button.hide()
            return
        caps_on = run_script("lockstatus.sh", "--caps-status") == "on"
        num_on = run_script("lockstatus.sh", "--num-status") == "on"
        self._set_lock_button_state(self.caps_lock_button, caps_on, "Caps Lock")
        self._set_lock_button_state(self.num_lock_button, num_on, "Num Lock")
        if self._caps_lock_on is not None and caps_on != self._caps_lock_on:
            self._send_lock_notification("Caps Lock", caps_on, 12345)
        if self._num_lock_on is not None and num_on != self._num_lock_on:
            self._send_lock_notification("Num Lock", num_on, 12346)
        self._caps_lock_on = caps_on
        self._num_lock_on = num_on

    def _poll_caffeine(self) -> None:
        caffeine_on = run_script("caffeine.sh", "status") == "on"
        self.caffeine_icon.setVisible(caffeine_on)
        self._apply_icon_to_widget(
            self.caffeine_icon, "coffee", material_icon("coffee"), 16
        )

    def _current_idle_milliseconds(self) -> int | None:
        idle_text = run_cmd(["xssstate", "-i"], timeout=1.0)
        if not idle_text:
            return None
        try:
            return max(0, int(idle_text))
        except Exception:
            return None

    def _locker_running(self) -> bool:
        for name in ("i3lock-color", "i3lock"):
            result = subprocess.run(
                ["pgrep", "-x", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                return True
        return False

    def _poll_autolock(self) -> None:
        settings = (
            self.autolock_settings if isinstance(self.autolock_settings, dict) else {}
        )
        if not bool(settings.get("enabled", True)):
            self._autolock_armed = True
            return
        if run_script("caffeine.sh", "status") == "on":
            self._autolock_armed = True
            return
        idle_ms = self._current_idle_milliseconds()
        if idle_ms is None:
            return
        if idle_ms < 1000:
            self._autolock_armed = True
            return
        if self._locker_running():
            self._autolock_armed = False
            return
        threshold_ms = max(1, int(settings.get("timeout_minutes", 2))) * 60 * 1000
        if idle_ms < threshold_ms:
            return
        if not self._autolock_armed or self._autolock_launch_pending:
            return
        command = lock_screen_command()
        if not command:
            return
        self._autolock_armed = False
        self._autolock_launch_pending = True
        try:
            run_bg_detached(command)
        finally:
            self._autolock_launch_pending = False

    def _detect_battery_base(self) -> Optional[Path]:
        power_supply = Path("/sys/class/power_supply")
        if not power_supply.exists():
            return None
        for candidate in sorted(power_supply.iterdir()):
            if not candidate.is_dir():
                continue
            if not candidate.name.startswith("BAT"):
                continue
            type_path = candidate / "type"
            if not type_path.exists():
                return candidate
            try:
                if type_path.read_text(encoding="utf-8").strip().lower() == "battery":
                    return candidate
            except OSError:
                continue
        return None

    def _poll_battery(self) -> None:
        if self._battery_base is None:
            self.battery_icon.hide()
            self.battery_value.hide()
            return

        try:
            with open(self._battery_base / "capacity", "r", encoding="utf-8") as handle:
                capacity = int(handle.read().strip())
            with open(self._battery_base / "status", "r", encoding="utf-8") as handle:
                status = handle.read().strip()
        except Exception:
            self.battery_icon.hide()
            self.battery_value.hide()
            return

        if status == "Charging":
            icon = "battery_charging_full"
        elif capacity >= 90:
            icon = "battery_full"
        elif capacity >= 65:
            icon = "battery_5_bar"
        elif capacity >= 40:
            icon = "battery_3_bar"
        elif capacity >= 20:
            icon = "battery_2_bar"
        else:
            icon = "battery_alert"

        self._apply_icon_to_widget(self.battery_icon, icon, material_icon(icon), 16)
        self.battery_value.setText(str(capacity))
        self.battery_icon.show()
        self.battery_value.show()

    def _goto_workspace(self, num: int) -> None:
        run_cmd(["i3-msg", "workspace", str(num)])
        self._poll_workspaces()

    def _toggle_notifications(self) -> None:
        if self._control_center_launch_pending:
            return
        active = (
            self._control_center_process is not None
            and self._control_center_process.poll() is None
        )
        if not active:
            active = any(
                background_match_exists(pattern)
                for pattern in entry_patterns(NOTIFICATION_CENTER)
            )
        if active:
            for pattern in entry_patterns(NOTIFICATION_CENTER):
                terminate_background_matches(pattern)
            if (
                self._control_center_process is not None
                and self._control_center_process.poll() is None
            ):
                self._control_center_process.terminate()
            self._control_center_process = None
            self.btn_control_center.setChecked(False)
            return

        if not NOTIFICATION_CENTER.exists():
            self.btn_control_center.setChecked(False)
            return

        self._control_center_launch_pending = True
        self.btn_control_center.setChecked(True)
        self.btn_control_center.setEnabled(False)
        QTimer.singleShot(450, self._finish_control_center_launch)
        try:
            for pattern in entry_patterns(NOTIFICATION_CENTER):
                terminate_background_matches(pattern)
            command = entry_command(NOTIFICATION_CENTER)
            if not command:
                raise RuntimeError("Notification center entrypoint not found")
            if not run_bg_detached(command):
                raise RuntimeError("Failed to launch notification center")
            self._control_center_process = None
        except Exception:
            self._control_center_process = None
            self._control_center_launch_pending = False
            self.btn_control_center.setEnabled(True)
            self.btn_control_center.setChecked(False)

    def _finish_control_center_launch(self) -> None:
        self._control_center_launch_pending = False
        self.btn_control_center.setEnabled(True)
        self._sync_control_center_button()

    def _python_bin(self) -> str:
        return python_executable()

    def _widget_launch_env(self) -> dict[str, str]:
        env = dict(os.environ)
        source_path = str(APP_DIR)
        existing = str(env.get("PYTHONPATH", "")).strip()
        if existing:
            parts = [part for part in existing.split(":") if part]
            if source_path not in parts:
                env["PYTHONPATH"] = f"{source_path}:{existing}"
        else:
            env["PYTHONPATH"] = source_path
        return env

    def _singleton_active(
        self, process: Optional[subprocess.Popen], script_path: Path | None
    ) -> bool:
        if process is not None and process.poll() is None:
            return True
        return False

    def _terminate_singleton_process(
        self, attr_name: str, script_path: Path | None
    ) -> None:
        process = getattr(self, attr_name, None)
        if process is not None and process.poll() is None:
            process.terminate()
        if script_path is not None:
            for pattern in entry_patterns(script_path):
                terminate_background_matches(pattern)
        setattr(self, attr_name, None)

    def _launch_singleton_process(
        self,
        attr_name: str,
        script_path: Path | None,
        *,
        python_bin: Optional[str] = None,
        extra_env: Optional[dict[str, str]] = None,
        cleanup_patterns: bool = True,
    ) -> bool:
        if script_path is None:
            setattr(self, attr_name, None)
            return False
        if (
            not script_path.exists()
            and entry_target(script_path) == script_path.resolve()
        ):
            setattr(self, attr_name, None)
            return False
        process = getattr(self, attr_name, None)
        if process is not None and process.poll() is None:
            self._terminate_singleton_process(attr_name, script_path)
        elif cleanup_patterns:
            self._terminate_singleton_process(attr_name, script_path)
        else:
            setattr(self, attr_name, None)
        try:
            if script_path.suffix == ".py":
                if python_bin is not None:
                    command = [python_bin, str(script_path)]
                else:
                    command = entry_command(script_path)
            elif python_bin is not None:
                command = [python_bin, str(script_path)]
            else:
                command = [str(script_path)]
            if not command:
                raise RuntimeError(f"No launch command available for {script_path}")
            env = self._widget_launch_env()
            if extra_env:
                env.update(extra_env)
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT.parents[1]),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            setattr(self, attr_name, None)
            return False
        setattr(self, attr_name, process)
        return True

    def _toggle_singleton_process(
        self,
        attr_name: str,
        script_path: Path | None,
        *,
        python_bin: Optional[str] = None,
        extra_env: Optional[dict[str, str]] = None,
        cleanup_patterns: bool = True,
    ) -> bool:
        if self._singleton_active(getattr(self, attr_name, None), script_path):
            self._terminate_singleton_process(attr_name, script_path)
            return False
        return self._launch_singleton_process(
            attr_name,
            script_path,
            python_bin=python_bin,
            extra_env=extra_env,
            cleanup_patterns=cleanup_patterns,
        )

    def _toggle_weather_popup(self) -> None:
        self._toggle_singleton_process(
            "_weather_popup_process", WEATHER_POPUP, python_bin=self._python_bin()
        )

    def _toggle_calendar_popup(self) -> None:
        self._toggle_singleton_process(
            "_calendar_popup_process", CALENDAR_POPUP, python_bin=self._python_bin()
        )

    def _toggle_wifi_popup(self) -> None:
        if WIFI_CONTROL is None or not WIFI_CONTROL.exists():
            self.net_icon.setChecked(False)
            return
        self._toggle_singleton_process(
            "_wifi_popup_process", WIFI_CONTROL, python_bin=self._python_bin()
        )
        QTimer.singleShot(150, self._sync_wifi_button)

    def _toggle_vpn_popup(self) -> None:
        if VPN_CONTROL is None or not VPN_CONTROL.exists():
            self.vpn_icon.setChecked(False)
            return
        self._toggle_singleton_process(
            "_vpn_popup_process", VPN_CONTROL, python_bin=self._python_bin()
        )
        QTimer.singleShot(150, self._sync_vpn_button)

    def _toggle_ai_popup(self) -> None:
        if AI_POPUP is None or not AI_POPUP.exists():
            self.ai_button.setChecked(False)
            return
        active = self._toggle_singleton_process(
            "_ai_popup_process",
            AI_POPUP,
            python_bin=self._python_bin(),
            cleanup_patterns=False,
        )
        self.ai_button.setChecked(active)

    def _open_region_settings(self) -> None:
        if not SETTINGS_PAGE.exists():
            return
        try:
            for pattern in entry_patterns(SETTINGS_PAGE):
                terminate_background_matches(pattern)
            command = entry_command(SETTINGS_PAGE, "--page", "region")
            if not command:
                return
            run_bg_detached(command)
        except Exception:
            pass

    def _toggle_lock_state(self, kind: str) -> None:
        if not LOCKSTATUS_SCRIPT.exists():
            return
        arg = "--toggle-caps" if kind == "caps" else "--toggle-num"
        try:
            subprocess.Popen(
                [str(LOCKSTATUS_SCRIPT), arg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            return
        QTimer.singleShot(180, self._poll_lock_states)

    def _open_christian_widget(self) -> None:
        if CHRISTIAN_WIDGET is None or not CHRISTIAN_WIDGET.exists():
            return
        self._toggle_singleton_process(
            "_christian_widget_process", CHRISTIAN_WIDGET, python_bin=self._python_bin()
        )

    def _open_health_widget(self) -> None:
        if HEALTH_WIDGET is None or not HEALTH_WIDGET.exists():
            return
        anchor = self.datetime_chip.mapToGlobal(self.datetime_chip.rect().bottomLeft())
        extra_env = {
            "HANAUTA_HEALTH_ANCHOR_X": str(
                anchor.x() + (self.datetime_chip.width() // 2)
            ),
            "HANAUTA_HEALTH_ANCHOR_Y": str(anchor.y() + 10),
        }
        self._toggle_singleton_process(
            "_health_widget_process",
            HEALTH_WIDGET,
            python_bin=self._python_bin(),
            extra_env=extra_env,
        )

    def _open_reminders_widget(self) -> None:
        if REMINDERS_WIDGET is None or not REMINDERS_WIDGET.exists():
            return
        self._toggle_singleton_process(
            "_reminders_widget_process", REMINDERS_WIDGET, python_bin=self._python_bin()
        )

    def _open_pomodoro_widget(self) -> None:
        if POMODORO_WIDGET is None or not POMODORO_WIDGET.exists():
            return
        self._toggle_singleton_process("_pomodoro_widget_process", POMODORO_WIDGET)

    def _open_rss_widget(self) -> None:
        rss_widget_script = resolve_rss_widget_script()
        if rss_widget_script is None or not rss_widget_script.exists():
            return
        self._toggle_singleton_process(
            "_rss_widget_process", rss_widget_script, python_bin=self._python_bin()
        )

    def _open_obs_widget(self) -> None:
        if OBS_WIDGET is None or not OBS_WIDGET.exists():
            return
        self._toggle_singleton_process(
            "_obs_widget_process", OBS_WIDGET, python_bin=self._python_bin()
        )

    def _open_crypto_widget(self) -> None:
        if CRYPTO_WIDGET is None or not CRYPTO_WIDGET.exists():
            return
        self._toggle_singleton_process(
            "_crypto_widget_process", CRYPTO_WIDGET, python_bin=self._python_bin()
        )

    def _open_cap_alerts_popup(self) -> None:
        if CAP_ALERTS_POPUP is None or not CAP_ALERTS_POPUP.exists():
            return
        self._toggle_singleton_process(
            "_cap_alerts_popup_process", CAP_ALERTS_POPUP, python_bin=self._python_bin()
        )

    def _open_vps_widget(self) -> None:
        if VPS_WIDGET is None or not VPS_WIDGET.exists():
            return
        self._toggle_singleton_process("_vps_widget_process", VPS_WIDGET)

    def _toggle_ntfy_popup(self) -> None:
        ntfy_popup_script = resolve_ntfy_popup_script()
        self._ntfy_popup_script = ntfy_popup_script
        if ntfy_popup_script is None or not ntfy_popup_script.exists():
            self.ntfy_button.setChecked(False)
            return
        active = self._toggle_singleton_process(
            "_ntfy_popup_process", ntfy_popup_script, python_bin=self._python_bin()
        )
        self.ntfy_button.setChecked(active)

    def _toggle_game_mode_popup(self) -> None:
        if GAME_MODE_POPUP is None or not GAME_MODE_POPUP.exists():
            self.game_mode_button.setChecked(False)
            return
        self._toggle_singleton_process(
            "_game_mode_popup_process", GAME_MODE_POPUP, python_bin=self._python_bin()
        )
        QTimer.singleShot(150, self._sync_game_mode_button)

    def _open_launcher(self) -> None:
        if LAUNCHER_SCRIPT.exists():
            run_bg_detached([str(LAUNCHER_SCRIPT)])
            return
        if not LAUNCHER_APP.exists():
            return
        self._toggle_singleton_process(
            "_launcher_process", LAUNCHER_APP, python_bin=self._python_bin()
        )

    def _toggle_powermenu(self) -> None:
        if not POWERMENU_WIDGET.exists():
            self.btn_power.setChecked(False)
            return
        active = self._toggle_singleton_process(
            "_powermenu_process", POWERMENU_WIDGET, python_bin=self._python_bin()
        )
        self.btn_power.setChecked(active)

    def _open_clipboard(self) -> None:
        run_bg([str(SCRIPTS_DIR / "openapps"), "--clip"])

    def _check_updates(self) -> None:
        anchor = self.datetime_chip.mapToGlobal(self.datetime_chip.rect().bottomLeft())
        extra_env = {
            "HANAUTA_UPDATES_ANCHOR_X": str(
                anchor.x() + (self.datetime_chip.width() // 2)
            ),
            "HANAUTA_UPDATES_ANCHOR_Y": str(anchor.y() + 10),
        }
        self._toggle_singleton_process(
            "_updates_widget_process",
            UPDATES_WIDGET,
            python_bin=self._python_bin(),
            extra_env=extra_env,
        )

    def _sync_ai_button(self) -> None:
        active = self._singleton_active(self._ai_popup_process, AI_POPUP)
        if not active:
            self._ai_popup_process = None
        self.ai_button.setChecked(active)

    def _sync_control_center_button(self) -> None:
        active = self._control_center_launch_pending or (
            self._control_center_process is not None
            and self._control_center_process.poll() is None
        )
        if not active:
            self._control_center_process = None
        self.btn_control_center.setChecked(active)

    def _sync_popup_button(
        self,
        button: QPushButton,
        process_attr: str,
        script_path: Path | None,
        *,
        tooltip: str | None = None,
    ) -> bool:
        process = getattr(self, process_attr, None)
        active = self._singleton_active(process, script_path)
        if not active:
            setattr(self, process_attr, None)
        button.setChecked(active)
        button.setProperty("active", active)
        if tooltip is not None:
            button.setToolTip(tooltip)
        button.update()
        return active

    def _sync_wifi_button(self) -> None:
        self._sync_popup_button(
            self.net_icon,
            "_wifi_popup_process",
            WIFI_CONTROL,
        )

    def _sync_vpn_button(self) -> None:
        self._sync_popup_button(
            self.vpn_icon,
            "_vpn_popup_process",
            VPN_CONTROL,
        )

    def _sync_weather_button(self) -> None:
        active = self._singleton_active(self._weather_popup_process, WEATHER_POPUP)
        if not active:
            self._weather_popup_process = None

    def _sync_ntfy_button(self) -> None:
        ntfy_popup_script = getattr(
            self, "_ntfy_popup_script", resolve_ntfy_popup_script()
        )
        active = self._singleton_active(self._ntfy_popup_process, ntfy_popup_script)
        if not active:
            self._ntfy_popup_process = None
        self.ntfy_button.setChecked(active)

    def _sync_game_mode_button(self) -> None:
        current = game_mode_summary()
        self._sync_popup_button(
            self.game_mode_button,
            "_game_mode_popup_process",
            GAME_MODE_POPUP,
            tooltip=str(current.get("note", "Game Mode")),
        )

    def _sync_powermenu_button(self) -> None:
        active = self._singleton_active(self._powermenu_process, POWERMENU_WIDGET)
        if not active:
            self._powermenu_process = None
        self.btn_power.setChecked(active)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._closing = True
        if self._status_overflow_popup is not None:
            self._status_overflow_popup.hide()
        if self._cava_worker is not None:
            self._cava_worker.stop()
            self._cava_worker.wait(500)
        if self._mail_worker is not None and self._mail_worker.isRunning():
            self._mail_worker.wait(500)
        if self._ai_popup_process is not None and self._ai_popup_process.poll() is None:
            self._ai_popup_process.terminate()
        if (
            self._control_center_process is not None
            and self._control_center_process.poll() is None
        ):
            self._control_center_process.terminate()
        if (
            self._wifi_popup_process is not None
            and self._wifi_popup_process.poll() is None
        ):
            self._wifi_popup_process.terminate()
        if (
            self._vpn_popup_process is not None
            and self._vpn_popup_process.poll() is None
        ):
            self._vpn_popup_process.terminate()
        if (
            self._weather_popup_process is not None
            and self._weather_popup_process.poll() is None
        ):
            self._weather_popup_process.terminate()
        if (
            self._christian_widget_process is not None
            and self._christian_widget_process.poll() is None
        ):
            self._christian_widget_process.terminate()
        if (
            self._health_widget_process is not None
            and self._health_widget_process.poll() is None
        ):
            self._health_widget_process.terminate()
        if (
            self._pomodoro_widget_process is not None
            and self._pomodoro_widget_process.poll() is None
        ):
            self._pomodoro_widget_process.terminate()
        if (
            self._rss_widget_process is not None
            and self._rss_widget_process.poll() is None
        ):
            self._rss_widget_process.terminate()
        if (
            self._obs_widget_process is not None
            and self._obs_widget_process.poll() is None
        ):
            self._obs_widget_process.terminate()
        if (
            self._updates_widget_process is not None
            and self._updates_widget_process.poll() is None
        ):
            self._updates_widget_process.terminate()
        if (
            self._crypto_widget_process is not None
            and self._crypto_widget_process.poll() is None
        ):
            self._crypto_widget_process.terminate()
        if (
            self._cap_alerts_popup_process is not None
            and self._cap_alerts_popup_process.poll() is None
        ):
            self._cap_alerts_popup_process.terminate()
        if (
            self._cap_alert_overlay_process is not None
            and self._cap_alert_overlay_process.poll() is None
        ):
            self._cap_alert_overlay_process.terminate()
        if (
            self._vps_widget_process is not None
            and self._vps_widget_process.poll() is None
        ):
            self._vps_widget_process.terminate()
        if (
            self._desktop_clock_process is not None
            and self._desktop_clock_process.poll() is None
        ):
            self._desktop_clock_process.terminate()
        if (
            self._ntfy_popup_process is not None
            and self._ntfy_popup_process.poll() is None
        ):
            self._ntfy_popup_process.terminate()
        if (
            self._game_mode_popup_process is not None
            and self._game_mode_popup_process.poll() is None
        ):
            self._game_mode_popup_process.terminate()
        self._run_bar_plugin_hooks("close")
        if (
            self._powermenu_process is not None
            and self._powermenu_process.poll() is None
        ):
            self._powermenu_process.terminate()
        super().closeEvent(event)

    def show(self) -> None:
        super().show()
        subprocess.run(
            ["pkill", "-x", "stalonetray"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        self._set_window_class()
        QTimer.singleShot(0, self._position_on_target_screen)
        QTimer.singleShot(150, self._apply_i3_window_rules)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_window_mask()
        if hasattr(self, "cap_alert_glow_frame"):
            self.cap_alert_glow_frame.setGeometry(self.cap_alert_chip.rect())

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)

    def _set_window_class(self) -> None:
        try:
            wid = int(self.winId())
            subprocess.run(
                [
                    "xprop",
                    "-id",
                    hex(wid),
                    "-f",
                    "_NET_WM_NAME",
                    "8t",
                    "-set",
                    "_NET_WM_NAME",
                    "CyberBar",
                ],
                check=False,
            )
            subprocess.run(
                [
                    "xprop",
                    "-id",
                    hex(wid),
                    "-f",
                    "WM_CLASS",
                    "8s",
                    "-set",
                    "WM_CLASS",
                    "CyberBar",
                ],
                check=False,
            )
        except Exception:
            pass

    def _apply_i3_window_rules(self) -> None:
        screen = self._target_screen()
        target_x = 0
        target_y = 0
        if screen is not None:
            geo = screen.availableGeometry()
            target_x = geo.x()
            target_y = geo.y()
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="CyberBar"]',
                    f"floating enable, sticky enable, move position {target_x} {target_y}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="CyberBar - Modern PyQt6 Top Bar")
    ap.add_argument("--ui", default="", help="Unused compatibility argument")
    ap.parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(antialias_font(app.font()))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    bar = CyberBar()
    bar.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
