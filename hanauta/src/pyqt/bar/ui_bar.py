#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyberBar - compact PyQt6 top bar aligned with the bar idea mock.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QByteArray, QEasingCurve, QFileSystemWatcher, QObject, QPoint, QProcess, QPropertyAnimation, QSize, Qt, QTimer, QThread, pyqtClassInfo, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QFontMetrics, QIcon, QPainter, QPalette, QPixmap, QRegion
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
REPO_ROOT = ROOT.parent
HANAUTA_ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime, rgba
from pyqt.shared.rss import collect_entries as collect_rss_entries
from pyqt.shared.rss import entry_fingerprint as rss_entry_fingerprint
from pyqt.shared.rss import load_cache as load_rss_cache
from pyqt.shared.rss import save_cache as save_rss_cache
from pyqt.shared.weather import AnimatedWeatherIcon, WeatherForecast, animated_icon_path, configured_city, fetch_forecast
from pyqt.shared.crypto import (
    fetch_prices as fetch_crypto_prices,
    load_settings_state as load_crypto_settings_state,
    load_tracker_state as load_crypto_tracker_state,
    movement_summary as crypto_movement_summary,
    save_tracker_state as save_crypto_tracker_state,
    should_check as crypto_should_check,
    slug_to_name as crypto_slug_to_name,
)
from pyqt.shared.gamemode import service_enabled as game_mode_service_enabled
from pyqt.shared.gamemode import summary as game_mode_summary

SCRIPTS_DIR = APP_DIR / "eww" / "scripts"
NOTIFICATION_CENTER = APP_DIR / "pyqt" / "notification-center" / "notification_center.py"
NOTIFICATION_CENTER_BINARY = HANAUTA_ROOT / "bin" / "hanauta-notification-center"
AI_POPUP = APP_DIR / "pyqt" / "ai-popup" / "ai_popup.py"
WIFI_CONTROL = APP_DIR / "pyqt" / "widget-wifi-control" / "wifi_control.py"
VPN_CONTROL = APP_DIR / "pyqt" / "widget-vpn-control" / "vpn_control.py"
CHRISTIAN_WIDGET = APP_DIR / "pyqt" / "widget-religion-christian" / "christian_widget.py"
REMINDERS_WIDGET = APP_DIR / "pyqt" / "widget-reminders" / "reminders_widget.py"
POMODORO_WIDGET = APP_DIR / "pyqt" / "widget-pomodoro" / "pomodoro_widget.py"
RSS_WIDGET = APP_DIR / "pyqt" / "widget-rss" / "rss_widget.py"
OBS_WIDGET = APP_DIR / "pyqt" / "widget-obs" / "obs_widget.py"
CRYPTO_WIDGET = APP_DIR / "pyqt" / "widget-crypto" / "crypto_widget.py"
VPS_WIDGET = APP_DIR / "pyqt" / "widget-vps" / "vps_widget.py"
DESKTOP_CLOCK_WIDGET = APP_DIR / "pyqt" / "widget-desktop-clock" / "desktop_clock_widget.py"
DESKTOP_CLOCK_BINARY = HANAUTA_ROOT / "bin" / "hanauta-clock"
NTFY_POPUP = APP_DIR / "pyqt" / "widget-ntfy-control" / "ntfy_popup.py"
WEATHER_POPUP = APP_DIR / "pyqt" / "widget-weather" / "weather_popup.py"
CALENDAR_POPUP = APP_DIR / "pyqt" / "widget-calendar" / "calendar_popup.py"
GAME_MODE_POPUP = APP_DIR / "pyqt" / "widget-game-mode" / "game_mode_popup.py"
SETTINGS_PAGE = APP_DIR / "pyqt" / "settings-page" / "settings.py"
ACTION_NOTIFICATION_SCRIPT = APP_DIR / "pyqt" / "shared" / "action_notification.py"
LAUNCHER_APP = APP_DIR / "pyqt" / "launcher" / "launcher.py"
POWERMENU_APP = HANAUTA_ROOT / "bin" / "hanauta-powermenu"
CAVA_BAR_CONFIG = APP_DIR / "pyqt" / "bar" / "cava_bar.conf"
FONTS_DIR = REPO_ROOT / "assets" / "fonts"
ASSETS_DIR = APP_DIR / "assets"
VPN_ICON_ON = ASSETS_DIR / "vpn_key.svg"
VPN_ICON_OFF = ASSETS_DIR / "vpn_key_off.svg"
CHRISTIAN_ICON = ASSETS_DIR / "cath.svg"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
BAR_ICON_CONFIG_DIR = Path.home() / ".config" / "hanauta"
BAR_ICON_CONFIG_FILE = BAR_ICON_CONFIG_DIR / "bar-icons.json"
BAR_ICON_EXAMPLE_FILE = ROOT / "hanauta" / "config" / "bar-icons.example.json"
LOCKSTATUS_SCRIPT = SCRIPTS_DIR / "lockstatus.sh"
TRAY_SLOT_WIDTH = 24
TRAY_SLOT_HEIGHT = 32
TRAY_SLOT_SIZE = 20
TRAY_ICON_SIZE = 16
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

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
    "dashboard": "\ue871",
    "music_note": "\ue405",
    "notifications": "\ue7f4",
    "notifications_active": "\ue7f7",
    "pause": "\ue034",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "public": "\ue80b",
    "videocam": "\ue04b",
    "show_chart": "\ue6e1",
    "timer": "\ue425",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "system_update": "\ue62a",
    "shield": "\ue9e0",
    "trip_origin": "\ue57b",
    "vpn_key": "\ue0da",
    "wifi": "\ue63e",
    "wifi_off": "\ue648",
    "sports_esports": "\uea28",
}

REMINDERS_BAR_GLYPH = "\ue003"


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
    try:
        subprocess.Popen(
            [str(script_path), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def run_bg(cmd: list[str]) -> None:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def widget_python() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


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


def background_match_exists(pattern: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
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
        if node.get("type") == "workspace" and str(node.get("name", "")).strip() == current_workspace:
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
    if DESKTOP_CLOCK_BINARY.exists():
        return DESKTOP_CLOCK_BINARY
    if DESKTOP_CLOCK_WIDGET.exists():
        return DESKTOP_CLOCK_WIDGET
    return None


def desktop_clock_command() -> list[str]:
    target = desktop_clock_target()
    if target is None:
        return []
    if target == DESKTOP_CLOCK_BINARY:
        return [str(target)]
    return [widget_python(), str(target)]


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
            BAR_ICON_CONFIG_FILE.write_text(BAR_ICON_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
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
        "ui_sans": FONTS_DIR / "InterVariable.ttf",
        "ui_display": FONTS_DIR / "Outfit-VariableFont_wght.ttf",
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


def tinted_svg_icon(path: Path, color: QColor, size: int = 16) -> QIcon:
    if not path.exists():
        return QIcon()
    renderer = QSvgRenderer()
    try:
        raw_svg = path.read_text(encoding="utf-8")
    except OSError:
        raw_svg = ""
    if raw_svg:
        normalized = (
            raw_svg.replace("param(fill)", "#FFFFFF")
            .replace("param(outline)", "#FFFFFF")
            .replace("param(fill-opacity)", "1")
            .replace("param(outline-opacity)", "1")
            .replace("param(outline-width)", "1.5")
        )
        renderer.load(QByteArray(normalized.encode("utf-8")))
    else:
        renderer.load(str(path))
    if not renderer.isValid():
        return QIcon()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)


def load_service_settings() -> dict[str, dict[str, object]]:
    try:
        raw = SETTINGS_FILE.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        return {}
    services = payload.get("services", {})
    return services if isinstance(services, dict) else {}


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


def load_bar_settings_from_payload(settings: object) -> dict[str, int]:
    current = settings.get("bar", {}) if isinstance(settings, dict) else {}
    current = current if isinstance(current, dict) else {}
    merged = dict(DEFAULT_BAR_SETTINGS)
    offset_keys = {"launcher_offset", "workspace_offset", "datetime_offset", "media_offset", "status_offset"}
    for key, default in DEFAULT_BAR_SETTINGS.items():
        if isinstance(default, bool):
            merged[key] = bool(current.get(key, default))
            continue
        try:
            merged[key] = int(current.get(key, default))
        except Exception:
            merged[key] = default
        if key in offset_keys:
            merged[key] = max(-8, min(8, int(merged[key])))
        elif key == "bar_height":
            merged[key] = max(32, min(72, int(merged[key])))
        else:
            merged[key] = max(0, min(32, int(merged[key])))
    return merged


def load_region_settings() -> dict[str, object]:
    return load_region_settings_from_payload(load_runtime_settings())


def load_bar_settings() -> dict[str, int]:
    return load_bar_settings_from_payload(load_runtime_settings())


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
        self.colors = {
            "focused": "#d0bcff",
            "occupied": "rgba(255,255,255,0.34)",
            "urgent": "#efb8c8",
            "empty": "rgba(255,255,255,0.14)",
        }
        self._apply_state()

    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = dict(colors)
        self._apply_state()

    def set_state(self, state: str) -> None:
        self.state = state
        self._apply_state()

    def _apply_state(self) -> None:
        size = 14 if self.state == "focused" else 10
        border = "1px solid rgba(255,255,255,0.18)" if self.state != "focused" else "none"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {self.colors.get(self.state, self.colors["empty"])};
                border: {border};
                border-radius: {size // 2}px;
                min-width: {size}px;
                max-width: {size}px;
                min-height: {size}px;
                max-height: {size}px;
            }}
            QPushButton:hover {{
                background: #e8def8;
            }}
            """
        )


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
        self.color = "#d0bcff"
        self._set_height(6)

    def set_color(self, color: str) -> None:
        self.color = color
        self._set_height(self.height())

    def _set_height(self, height: int) -> None:
        self.setFixedHeight(height)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {self.color};
                border-radius: 2px;
                min-height: {height}px;
                max-height: {height}px;
            }}
            """
        )

    def set_level(self, level: float) -> None:
        height = 4 + int(max(0.0, min(1.0, level)) * 12)
        self._set_height(height)


@pyqtClassInfo("D-Bus Interface", "org.kde.StatusNotifierWatcher")
class StatusNotifierWatcher(QObject):
    statusNotifierItemRegistered = pyqtSignal(str, name="StatusNotifierItemRegistered")
    statusNotifierItemUnregistered = pyqtSignal(str, name="StatusNotifierItemUnregistered")
    statusNotifierHostRegistered = pyqtSignal(name="StatusNotifierHostRegistered")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[str] = []

    @pyqtSlot(str)
    def RegisterStatusNotifierItem(self, service_or_path: str) -> None:
        item_id = service_or_path.strip()
        if not item_id:
            return
        if item_id not in self._items:
            self._items.append(item_id)
            self.statusNotifierItemRegistered.emit(item_id)

    @pyqtSlot(str)
    def RegisterStatusNotifierHost(self, _service: str) -> None:
        self.statusNotifierHostRegistered.emit()

    @pyqtProperty("QStringList")
    def RegisteredStatusNotifierItems(self) -> list[str]:
        return list(self._items)

    @pyqtProperty(bool)
    def IsStatusNotifierHostRegistered(self) -> bool:
        return True

    @pyqtProperty(int)
    def ProtocolVersion(self) -> int:
        return 0

    def unregister_item(self, item_id: str) -> None:
        if item_id in self._items:
            self._items.remove(item_id)
            self.statusNotifierItemUnregistered.emit(item_id)


class StatusNotifierItemButton(QPushButton):
    def __init__(self, item_id: str, bus: QDBusConnection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.bus = bus
        self.service, self.path = self._parse_item_id(item_id)
        self.iface = QDBusInterface(self.service, self.path, "org.kde.StatusNotifierItem", self.bus)
        self.setObjectName("trayButton")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(24, 24)
        self.refresh()
        for signal_name in ("NewIcon", "NewTitle", "NewToolTip", "NewStatus"):
            self.bus.connect(self.service, self.path, "org.kde.StatusNotifierItem", signal_name, self.refresh)

    @staticmethod
    def _parse_item_id(item_id: str) -> tuple[str, str]:
        if "/" in item_id:
            service, path = item_id.split("/", 1)
            return service, f"/{path}"
        return item_id, "/StatusNotifierItem"

    @pyqtSlot()
    def refresh(self) -> None:
        title = self.iface.property("Title") or self.service
        icon_name = self.iface.property("IconName") or ""
        status = str(self.iface.property("Status") or "")
        self.setToolTip(str(title))
        icon = QIcon.fromTheme(str(icon_name))
        if not icon.isNull():
            self.setIcon(icon)
            self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText(str(title)[:1].upper())
        self.setVisible(status != "Passive")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton:
            self.iface.call("ContextMenu", 0, 0)
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self.iface.call("SecondaryActivate", 0, 0)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.iface.call("Activate", 0, 0)
            event.accept()
            return
        super().mousePressEvent(event)


class StatusNotifierTray(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("trayHost")
        self.bus = QDBusConnection.sessionBus()
        self.watcher_service = "org.kde.StatusNotifierWatcher"
        self.host_service = f"org.kde.StatusNotifierHost-{os.getpid()}-1"
        self._owns_watcher_service = False
        self._watcher_object: StatusNotifierWatcher | None = None
        self.buttons: dict[str, StatusNotifierItemButton] = {}
        self.proxy: QDBusInterface | None = None

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 4, 8, 4)
        self.layout.setSpacing(4)
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
        else:
            if not self._owns_watcher_service and self.bus.registerService(self.watcher_service):
                self._watcher_object = StatusNotifierWatcher()
                self.bus.registerObject(
                    "/StatusNotifierWatcher",
                    self._watcher_object,
                    QDBusConnection.RegisterOption.ExportAllSlots
                    | QDBusConnection.RegisterOption.ExportAllSignals
                    | QDBusConnection.RegisterOption.ExportAllProperties,
                )
                self._owns_watcher_service = True
                self.proxy = QDBusInterface(
                    self.watcher_service,
                    "/StatusNotifierWatcher",
                    self.watcher_service,
                    self.bus,
                )
            else:
                self.proxy = None

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
        items = self.proxy.property("RegisteredStatusNotifierItems") or []
        if isinstance(items, list):
            for item_id in items:
                self._register_item(str(item_id))
        self._sync_visibility()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.bus.unregisterService(self.host_service)
        if self._owns_watcher_service:
            self.bus.unregisterObject("/StatusNotifierWatcher")
            self.bus.unregisterService(self.watcher_service)
        super().closeEvent(event)

    @pyqtSlot(str)
    def _register_item(self, item_id: str) -> None:
        if item_id in self.buttons:
            self.buttons[item_id].refresh()
            self._sync_visibility()
            return
        button = StatusNotifierItemButton(item_id, self.bus, self)
        self.buttons[item_id] = button
        self.layout.addWidget(button)
        self._sync_visibility()

    @pyqtSlot(str)
    def _unregister_item(self, item_id: str) -> None:
        button = self.buttons.pop(item_id, None)
        if button is not None:
            self.layout.removeWidget(button)
            button.deleteLater()
        self._sync_visibility()

    @pyqtSlot(str, str, str)
    def _handle_name_owner_changed(self, name: str, _old_owner: str, new_owner: str) -> None:
        if not name.startswith("org.") and not name.startswith(":"):
            return
        if not new_owner:
            to_remove = [item_id for item_id, button in self.buttons.items() if button.service == name]
            for item_id in to_remove:
                self._unregister_item(item_id)

    def _sync_visibility(self) -> None:
        visible_buttons = 0
        for button in self.buttons.values():
            button.refresh()
            if button.isVisible():
                visible_buttons += 1
        self.setVisible(visible_buttons > 0)


class WeatherWorker(QThread):
    loaded = pyqtSignal(object)

    def run(self) -> None:
        city = configured_city()
        if city is None:
            self.loaded.emit(None)
            return
        self.loaded.emit(fetch_forecast(city))


class CyberBar(QWidget):
    def __init__(self, ui_path: Optional[Path] = None):
        super().__init__()
        self.ui_path = ui_path
        self.loaded_fonts = load_app_fonts()
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self._settings_mtime = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        self.runtime_settings = normalize_runtime_settings(load_runtime_settings())
        services = self.runtime_settings.get("services", {})
        self.service_settings = services if isinstance(services, dict) else {}
        self.bar_settings = load_bar_settings_from_payload(self.runtime_settings)
        self.region_settings = load_region_settings_from_payload(self.runtime_settings)
        self.ui_font = detect_font(
            "Rubik",
            self.loaded_fonts.get("ui_sans", ""),
            "Inter",
            "Noto Sans",
            "Sans Serif",
        )
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
        self._cava_process: Optional[QProcess] = None
        self._ai_popup_process: Optional[subprocess.Popen] = None
        self._launcher_process: Optional[subprocess.Popen] = None
        self._control_center_process: Optional[subprocess.Popen] = None
        self._wifi_popup_process: Optional[subprocess.Popen] = None
        self._vpn_popup_process: Optional[subprocess.Popen] = None
        self._christian_widget_process: Optional[subprocess.Popen] = None
        self._reminders_widget_process: Optional[subprocess.Popen] = None
        self._pomodoro_widget_process: Optional[subprocess.Popen] = None
        self._rss_widget_process: Optional[subprocess.Popen] = None
        self._obs_widget_process: Optional[subprocess.Popen] = None
        self._crypto_widget_process: Optional[subprocess.Popen] = None
        self._vps_widget_process: Optional[subprocess.Popen] = None
        self._desktop_clock_process: Optional[subprocess.Popen] = None
        self._ntfy_popup_process: Optional[subprocess.Popen] = None
        self._weather_popup_process: Optional[subprocess.Popen] = None
        self._calendar_popup_process: Optional[subprocess.Popen] = None
        self._game_mode_popup_process: Optional[subprocess.Popen] = None
        self._powermenu_process: Optional[subprocess.Popen] = None
        self._weather_worker: Optional[WeatherWorker] = None
        self._weather_forecast: Optional[WeatherForecast] = None
        self._cava_buffer = ""
        self._battery_base: Optional[Path] = self._detect_battery_base()
        self._settings_watcher: Optional[QFileSystemWatcher] = None
        self._settings_reload_timer: Optional[QTimer] = None
        self._control_center_launch_pending = False
        self._bar_icon_overrides = load_bar_icon_overrides()
        self._caps_lock_on: Optional[bool] = None
        self._num_lock_on: Optional[bool] = None
        self._rss_last_interval_ms = 0
        self._crypto_last_interval_ms = 0
        self._setup_window()
        self._build_ui()
        self._apply_bar_icon_overrides()
        self._apply_styles()
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

        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.setFixedSize(geo.width(), int(self.bar_settings.get("bar_height", 40)))
        self.move(geo.x(), geo.y())

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
        self.left_layout = QHBoxLayout(left_wrap)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        self.launcher_chip = QFrame()
        self.launcher_chip.setObjectName("launcherChip")
        self.launcher_layout = QHBoxLayout(self.launcher_chip)
        self.launcher_layout.setContentsMargins(8, 4, 8, 4)  # top/bottom margins move the row vertically
        self.launcher_layout.setSpacing(6)  # spacing only changes the horizontal gap
        self.launcher_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.ai_button = self._icon_button("auto_awesome")
        self.ai_button.setObjectName("aiToggleButton")
        self.ai_button.setCheckable(True)
        self.ai_button.clicked.connect(self._toggle_ai_popup)
        self.launcher_trigger = ClickableFrame()
        self.launcher_trigger.setObjectName("launcherTrigger")
        self.launcher_trigger.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.launcher_trigger.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.launcher_trigger.setFixedHeight(20)
        self.launcher_trigger.clicked.connect(self._open_launcher)
        self.launcher_trigger.hoveredChanged.connect(self._update_launcher_wordmark_colors)
        self.launcher_trigger_layout = QHBoxLayout(self.launcher_trigger)
        self.launcher_trigger_layout.setContentsMargins(10, 0, 10, 2)
        self.launcher_trigger_layout.setSpacing(5)
        self.launcher_trigger_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.launcher_note = QLabel("♪")
        self.launcher_note.setObjectName("launcherNote")
        self.launcher_note.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        self.launcher_note.setFixedSize(12, 16)
        self.launcher_text = QLabel("hanauta")
        self.launcher_text.setObjectName("launcherText")
        self.launcher_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.launcher_text.setFixedHeight(15)
        self.launcher_trigger_layout.addWidget(self.launcher_note)
        self.launcher_trigger_layout.addWidget(self.launcher_text)
        self.launcher_layout.addWidget(self.ai_button)
        self.launcher_layout.addWidget(self.launcher_trigger)
        self.launcher_layout.setAlignment(self.ai_button, Qt.AlignmentFlag.AlignVCenter)
        self.launcher_layout.setAlignment(self.launcher_trigger, Qt.AlignmentFlag.AlignVCenter)
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
        for ws_num in range(1, 6):
            dot = WorkspaceDot(ws_num, self._goto_workspace)
            self.workspace_buttons[ws_num] = dot
            self.dots_layout.addWidget(dot)
        self.workspace_layout.addWidget(dots_wrap)
        self.workspace_wrap = self._wrap_movable(self.workspace_chip)
        self.left_layout.addWidget(self.workspace_wrap)
        self.root_layout.addWidget(left_wrap, 0, Qt.AlignmentFlag.AlignLeft)

        center_wrap = QWidget()
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
        self.locale_button = QPushButton(self._icon_text("public"))
        self.locale_button.setObjectName("utilityButton")
        self.locale_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.locale_button.setFont(QFont(self.material_font, 18))
        self.locale_button.clicked.connect(self._open_region_settings)
        self.datetime_layout.addWidget(self.weather_icon)
        self.datetime_layout.addWidget(self.time_label)
        self.datetime_layout.addWidget(self.date_label)
        self.datetime_layout.addWidget(self.locale_button)
        self.btn_control_center = self._icon_button("dashboard")
        self.btn_control_center.setObjectName("utilityButton")
        self.btn_control_center.setCheckable(True)
        self.btn_control_center.clicked.connect(self._toggle_notifications)
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
        self.media_text = QLabel("Nothing playing")
        self.media_text.setObjectName("mediaText")
        self.media_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
        self.right_layout = QHBoxLayout(right_wrap)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)

        self.status_chip = QFrame()
        self.status_chip.setObjectName("statusChip")
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
        for label in (self.net_icon, self.vpn_icon, self.pomodoro_button, self.rss_button, self.obs_button, self.crypto_button, self.ntfy_button, self.game_mode_button, self.battery_icon, self.caffeine_icon):
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
        self.btn_updates = self._icon_button("system_update")
        self.btn_updates.setObjectName("statusIconButton")
        self.btn_updates.clicked.connect(self._check_updates)
        self.btn_power = self._icon_button("power_settings_new")
        self.btn_power.setObjectName("statusIconButton")
        self.btn_power.setCheckable(True)
        self.btn_power.clicked.connect(self._toggle_powermenu)

        self.tray_host = StatusNotifierTray(self)
        self.tray_host.setProperty("embedded", True)
        self.tray_host.setToolTip("Qt StatusNotifier tray")
        self.status_layout.addWidget(self.btn_clip)
        self.status_layout.addWidget(self.btn_updates)
        self.status_layout.addWidget(self.tray_host)
        self.status_layout.addWidget(self.btn_power)
        self.status_wrap = self._wrap_movable(self.status_chip)
        self.right_layout.addWidget(self.status_wrap)
        self.root_layout.addWidget(right_wrap, 0, Qt.AlignmentFlag.AlignRight)

        has_battery = self._battery_base is not None
        self.caffeine_icon.setVisible(False)
        self.battery_icon.setVisible(has_battery)
        self.battery_value.setVisible(has_battery)
        self._set_vpn_button_icon(False)
        self._set_christian_button_icon()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._apply_bar_settings()
        self._install_debug_tooltips()

    def _icon_button(self, icon_name: str) -> QPushButton:
        button = QPushButton(self._icon_text(icon_name))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setToolTip(f"IconButton {icon_name}")
        button.setProperty("iconKey", icon_name)
        return button

    def _icon_text(self, icon_name: str) -> str:
        return self._bar_icon_overrides.get(icon_name, material_icon(icon_name))

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

    def _icon_font_for_text(self, icon_key: str, text: str, fallback_text: str, size: int) -> tuple[QFont, bool, str]:
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

    def _apply_icon_to_widget(self, widget: QWidget, icon_key: str, fallback_text: str, size: int = 16) -> None:
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
                    pixmap = QPixmap(str(path)).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    widget.setPixmap(pixmap)
                    return
        if isinstance(widget, QPushButton):
            text = override or fallback_text
            font, nerd_icon, resolved_text = self._icon_font_for_text(icon_key, text, fallback_text, size)
            widget.setProperty("iconKey", icon_key)
            widget.setProperty("nerdIcon", nerd_icon)
            widget.setFont(font)
            widget.setIcon(QIcon())
            widget.setText(resolved_text)
        elif isinstance(widget, QLabel):
            text = override or fallback_text
            font, _, resolved_text = self._icon_font_for_text(icon_key, text, fallback_text, size)
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
        self._settings_watcher.fileChanged.connect(self._queue_settings_reload)
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

    def _queue_settings_reload(self) -> None:
        if self._settings_reload_timer is None:
            return
        self._settings_reload_timer.start(40)

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
        self.btn_control_center.setToolTip("Control center button")
        self.media_chip.setToolTip("Media chip")
        self.media_icon.setToolTip("Media icon")
        self.media_equalizer.setToolTip("Media equalizer")
        self.media_text.setToolTip("Media text")
        self.media_prev.setToolTip("Media previous button")
        self.media_play.setToolTip("Media play/pause button")
        self.media_next.setToolTip("Media next button")
        self.status_chip.setToolTip("Status chip")
        self.net_icon.setToolTip("Wi-Fi button")
        self.vpn_icon.setToolTip("VPN button")
        self.christian_button.setToolTip("Christian widget button")
        self.reminders_button.setToolTip("Reminders widget button")
        self.ntfy_button.setToolTip("ntfy publisher button")
        self.caffeine_icon.setToolTip("Caffeine icon")
        self.battery_icon.setToolTip("Battery icon")
        self.battery_value.setToolTip("Battery value")
        self.btn_clip.setToolTip("Clipboard button")
        self.btn_updates.setToolTip("Updates button")
        self.tray_host.setToolTip("Qt StatusNotifier tray")
        self.btn_power.setToolTip("Power button")

    def _apply_bar_settings(self) -> None:
        self.bar_settings = load_bar_settings()
        merge_all_chips = bool(self.bar_settings.get("merge_all_chips", False))
        bar_height = int(self.bar_settings.get("bar_height", 40))
        outer_vertical_margin = 4
        surface_height = max(24, bar_height - (outer_vertical_margin * 2))
        chip_vertical_padding = max(4, min(14, (surface_height - 22) // 2))
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.setFixedSize(geo.width(), bar_height)
            self.move(geo.x(), geo.y())
        self.outer_layout.setContentsMargins(12, outer_vertical_margin, 12, outer_vertical_margin)
        self.bar_surface.setFixedHeight(surface_height)
        self.root_layout.setSpacing(0 if merge_all_chips else 14)
        self.left_layout.setSpacing(0 if merge_all_chips else 10)
        self.center_layout.setSpacing(0 if merge_all_chips else 10)
        self.right_layout.setSpacing(0 if merge_all_chips else 8)
        self.root_layout.setContentsMargins(8, 0, 8, 0)
        for chip in (
            self.launcher_chip,
            self.workspace_chip,
            self.datetime_chip,
            self.media_chip,
            self.status_chip,
        ):
            chip.setFixedHeight(surface_height)
        self.launcher_layout.setContentsMargins(8, chip_vertical_padding, 8, chip_vertical_padding)
        self.workspace_layout.setContentsMargins(12, chip_vertical_padding, 12, chip_vertical_padding)
        self.datetime_layout.setContentsMargins(12, chip_vertical_padding, 12, chip_vertical_padding)
        self.media_layout.setContentsMargins(14, chip_vertical_padding, 14, chip_vertical_padding)
        self.status_layout.setContentsMargins(10, chip_vertical_padding, 10, chip_vertical_padding)
        self._apply_vertical_offset(self.ai_wrap, self.bar_settings.get("launcher_offset", 0))
        self._apply_vertical_offset(self.launcher_wrap, self.bar_settings.get("launcher_offset", 0))
        self._apply_vertical_offset(self.workspace_wrap, self.bar_settings.get("workspace_offset", 0))
        self._apply_vertical_offset(self.datetime_wrap, self.bar_settings.get("datetime_offset", 0))
        self._apply_vertical_offset(self.media_wrap, self.bar_settings.get("media_offset", 0))
        self._apply_vertical_offset(self.status_wrap, self.bar_settings.get("status_offset", 0))

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
        chip_bg = "transparent" if merge_all_chips else rgba(theme.surface_container_high, 0.78)
        chip_border = "transparent" if merge_all_chips else rgba(theme.outline, 0.18)
        media_bg = "transparent" if merge_all_chips else rgba(theme.surface_container, 0.86)
        media_border = "transparent" if merge_all_chips else rgba(theme.outline, 0.20)
        full_bar_bg = rgba(theme.surface_container, 0.90) if merge_all_chips else "transparent"
        full_bar_border = rgba(theme.outline, 0.20) if merge_all_chips else "transparent"
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
            #statusChip {{
                background: {media_bg};
                border: 1px solid {media_border};
                border-radius: {chip_radius_css};
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
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.3px;
                padding-bottom: 3px;
            }}
            QLabel#launcherText {{
                font-family: "{self.ui_font}";
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.6px;
                padding-bottom: 3px;
            }}
            #launcherChip:hover {{
                background: {rgba(theme.surface_container_high, 0.92)};
                border: 1px solid {rgba(theme.primary, 0.20)};
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
            #mediaControl:hover, #utilityButton:hover, #aiToggleButton:hover {{
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
                min-width: 22px;
                max-width: 22px;
                padding: 0;
            }}
            #launcherChip QPushButton#aiToggleButton:hover,
            #launcherChip QFrame#launcherTrigger:hover {{
                background: {theme.hover_bg};
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #launcherChip QFrame#launcherTrigger:hover QLabel#launcherNote,
            #launcherChip QFrame#launcherTrigger:hover QLabel#launcherText {{
                color: {theme.text};
            }}
            #aiToggleButton:checked {{
                color: {theme.primary};
                background: {theme.accent_soft};
                border-radius: {max(0, chip_radius - 5)}px;
            }}
            #timeLabel {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 600;
                padding-right: 2px;
            }}
            #dateLabel {{
                color: {theme.text_muted};
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
        self._sync_ntfy_button_visibility()
        self._sync_desktop_clock_process()
        self._update_locale_button()
        self._update_window_mask()

    def _update_launcher_wordmark_colors(self, hovered: bool = False) -> None:
        note_color = self.theme.text if hovered else self.theme.primary
        text_color = self.theme.text if hovered else self.theme.text_muted
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

    def _set_lock_button_state(self, button: QPushButton, active: bool, title: str) -> None:
        button.setProperty("active", active)
        button.setVisible(active)
        button.setToolTip(f"{title}: {'On' if active else 'Off'}")
        self.style().unpolish(button)
        self.style().polish(button)

    def _send_lock_notification(self, title: str, enabled: bool, replace_id: int) -> None:
        state_text = "Enabled" if enabled else "Disabled"
        try:
            subprocess.Popen(
                ["notify-send", "-r", str(replace_id), title, state_text],
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
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()
        self._reload_settings_if_needed()

    def _reload_settings_if_needed(self, force: bool = False) -> None:
        current_mtime = SETTINGS_FILE.stat().st_mtime if SETTINGS_FILE.exists() else 0.0
        icon_mtime = BAR_ICON_CONFIG_FILE.stat().st_mtime if BAR_ICON_CONFIG_FILE.exists() else 0.0
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
        self._apply_bar_settings()
        self._apply_bar_icon_overrides()
        self._apply_styles()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._sync_desktop_clock_process()
        self._update_locale_button()

    def _apply_bar_icon_overrides(self) -> None:
        self._apply_icon_to_widget(self.locale_button, "public", material_icon("public"), 16)
        self._apply_icon_to_widget(self.media_icon, "music_note", material_icon("music_note"), 16)
        self._apply_icon_to_widget(self.pomodoro_button, "timer", material_icon("timer"), 16)
        self._apply_icon_to_widget(self.rss_button, "public", material_icon("public"), 16)
        self._apply_icon_to_widget(self.obs_button, "videocam", material_icon("videocam"), 16)
        self._apply_icon_to_widget(self.crypto_button, "show_chart", material_icon("show_chart"), 16)
        self._apply_icon_to_widget(self.ntfy_button, "notifications", material_icon("notifications"), 16)
        self._apply_icon_to_widget(self.game_mode_button, "sports_esports", material_icon("sports_esports"), 16)
        self._apply_icon_to_widget(self.caffeine_icon, "coffee", material_icon("coffee"), 16)
        self._apply_icon_to_widget(self.btn_clip, "content_paste", material_icon("content_paste"), 16)
        self._apply_icon_to_widget(self.btn_updates, "system_update", material_icon("system_update"), 16)
        self._apply_icon_to_widget(self.btn_power, "power_settings_new", material_icon("power_settings_new"), 16)
        self._apply_icon_to_widget(self.launcher_note, "launcher_note", "♪", 14)
        self._set_vpn_button_icon(self.vpn_icon.property("active") == True)
        self._set_christian_button_icon()

    def _update_window_mask(self) -> None:
        self.setMask(QRegion(self.rect()))

    def _start_polls(self) -> None:
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

        self.settings_timer = QTimer(self)
        self.settings_timer.timeout.connect(self._reload_settings_if_needed)
        self.settings_timer.start(800)

        self.ai_popup_timer = QTimer(self)
        self.ai_popup_timer.timeout.connect(self._sync_ai_button)
        self.ai_popup_timer.start(1000)

        self.control_center_timer = QTimer(self)
        self.control_center_timer.timeout.connect(self._sync_control_center_button)
        self.control_center_timer.start(1000)

        self.wifi_popup_timer = QTimer(self)
        self.wifi_popup_timer.timeout.connect(self._sync_wifi_button)
        self.wifi_popup_timer.start(1000)

        self.vpn_popup_timer = QTimer(self)
        self.vpn_popup_timer.timeout.connect(self._sync_vpn_button)
        self.vpn_popup_timer.start(1000)

        self.ntfy_popup_timer = QTimer(self)
        self.ntfy_popup_timer.timeout.connect(self._sync_ntfy_button)
        self.ntfy_popup_timer.start(1000)

        self.game_mode_popup_timer = QTimer(self)
        self.game_mode_popup_timer.timeout.connect(self._sync_game_mode_button)
        self.game_mode_popup_timer.start(1000)

        self.weather_popup_timer = QTimer(self)
        self.weather_popup_timer.timeout.connect(self._sync_weather_button)
        self.weather_popup_timer.start(1000)

        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self._poll_weather)
        self.weather_timer.start(900000)

        self.rss_notify_timer = QTimer(self)
        self.rss_notify_timer.timeout.connect(self._poll_rss_notifications)
        self.rss_notify_timer.start(60000)

        self.crypto_timer = QTimer(self)
        self.crypto_timer.timeout.connect(self._poll_crypto_notifications)
        self.crypto_timer.start(60000)

        self.powermenu_timer = QTimer(self)
        self.powermenu_timer.timeout.connect(self._sync_powermenu_button)
        self.powermenu_timer.start(1000)

        self._start_cava()

    def _poll_all(self) -> None:
        self._poll_clock()
        self._poll_workspaces()
        self._poll_media()
        self._poll_system()
        self._poll_weather()
        self._poll_rss_notifications()
        self._poll_crypto_notifications()
        self._sync_game_mode_button()

    def _poll_clock(self) -> None:
        now = datetime.now()
        self.time_label.setText(self._format_time_text(now))
        self.date_label.setText(self._format_date_text(now))

    def _poll_workspaces(self) -> None:
        result = run_cmd(["i3-msg", "-t", "get_workspaces"])
        if not result:
            return
        try:
            workspaces = json.loads(result)
        except Exception:
            return

        focused_num = 1
        occupied = set()
        urgent = set()
        for ws in workspaces:
            num = int(ws.get("num", 0))
            if num > 0:
                occupied.add(num)
            if ws.get("focused"):
                focused_num = num
            if ws.get("urgent"):
                urgent.add(num)

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
        self._sync_desktop_clock_process()

    def _poll_media(self) -> None:
        title = run_script("mpris.sh", "title")
        status = run_script("mpris.sh", "status")
        artist = run_script("mpris.sh", "artist")
        has_media = bool(title and title != "Play Something")

        if has_media:
            display = f"{artist} - {title}" if artist else title
            self.media_text.setText(display[:42] + "…" if len(display) > 42 else display)
            self.media_play.setText(material_icon("pause" if status == "Playing" else "play_arrow"))
        else:
            self.media_text.setText("Nothing playing")
            self.media_play.setText(material_icon("play_arrow"))

        self._media_playing = status == "Playing" and has_media
        self.media_chip.setProperty("active", self._media_playing)
        self.style().unpolish(self.media_chip)
        self.style().polish(self.media_chip)
        self._update_media_equalizer_color()
        self._animate_media(has_media)

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
        if self._cava_process is not None:
            self._cava_process.kill()
            self._cava_process.deleteLater()

        self._cava_process = QProcess(self)
        self._cava_process.setProgram("/usr/bin/cava")
        self._cava_process.setArguments(["-p", str(CAVA_BAR_CONFIG)])
        self._cava_process.readyReadStandardOutput.connect(self._read_cava_output)
        self._cava_process.finished.connect(self._handle_cava_exit)
        self._cava_process.start()

    def _read_cava_output(self) -> None:
        if self._cava_process is None:
            return
        chunk = bytes(self._cava_process.readAllStandardOutput()).decode("utf-8", errors="ignore")
        if not chunk:
            return
        self._cava_buffer += chunk
        while "\n" in self._cava_buffer:
            frame, self._cava_buffer = self._cava_buffer.split("\n", 1)
            self._apply_cava_frame(frame.strip())

    def _apply_cava_frame(self, frame: str) -> None:
        if not frame:
            return
        parts = [part for part in frame.split(";") if part != ""]
        if not parts:
            return

        values: list[float] = []
        for part in parts[: len(self.equalizer_bars)]:
            try:
                values.append(max(0.0, min(1.0, int(part) / 100.0)))
            except ValueError:
                values.append(0.0)

        if not self._media_playing:
            values = [0.08 for _ in values]

        for bar, level in zip(self.equalizer_bars, values):
            bar.set_level(level)

    def _handle_cava_exit(self) -> None:
        QTimer.singleShot(1000, self._start_cava)

    def _poll_system(self) -> None:
        self._poll_network()
        self._poll_caffeine()
        self._poll_battery()
        self._poll_lock_states()
        self._sync_christian_button_visibility()
        self._sync_reminders_button_visibility()
        self._sync_pomodoro_button_visibility()
        self._sync_rss_button_visibility()
        self._sync_obs_button_visibility()
        self._sync_crypto_button_visibility()
        self._sync_ntfy_button_visibility()
        self._sync_game_mode_button_visibility()
        self._sync_weather_visibility()

    def _poll_weather(self) -> None:
        if self._weather_worker is not None and self._weather_worker.isRunning():
            return
        if configured_city() is None:
            self._weather_forecast = None
            self._sync_weather_visibility()
            return
        self._weather_worker = WeatherWorker()
        self._weather_worker.loaded.connect(self._apply_weather_forecast)
        self._weather_worker.finished.connect(self._finish_weather_worker)
        self._weather_worker.start()

    def _apply_weather_forecast(self, forecast: object) -> None:
        self._weather_forecast = forecast if isinstance(forecast, WeatherForecast) else None
        if self._weather_forecast is not None:
            current = self._weather_forecast.current
            self.weather_icon.set_icon_path(animated_icon_path(current.icon_name))
            self.weather_icon.setToolTip(
                f"{self._weather_forecast.city.label} • {round(current.temperature):.0f}° • {current.condition}"
            )
        self._sync_weather_visibility()

    def _finish_weather_worker(self) -> None:
        self._weather_worker = None

    def _send_action_notification(
        self,
        summary: str,
        body: str,
        action_label: str,
        open_url: str,
        replace_id: int,
    ) -> None:
        if not ACTION_NOTIFICATION_SCRIPT.exists() or not open_url.strip():
            try:
                subprocess.Popen(
                    ["notify-send", summary, body],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception:
                pass
            return
        run_bg(
            [
                widget_python(),
                str(ACTION_NOTIFICATION_SCRIPT),
                "--app-name",
                "Hanauta",
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
            ]
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
        settings = load_crypto_settings_state()
        services = settings.get("services", {})
        crypto_settings = settings.get("crypto", {})
        if not isinstance(services, dict) or not isinstance(crypto_settings, dict):
            return
        service = services.get("crypto_widget", {})
        if not isinstance(service, dict) or not bool(service.get("enabled", True)):
            return
        if not bool(crypto_settings.get("notify_price_moves", True)):
            return
        interval = max(5, int(crypto_settings.get("check_interval_minutes", 15) or 15))
        state = load_crypto_tracker_state()
        if not crypto_should_check(str(state.get("last_checked_at", "")), interval):
            return
        try:
            prices = fetch_crypto_prices(settings)
        except Exception:
            return
        previous = state.get("last_prices", {})
        if not isinstance(previous, dict):
            previous = {}
        up_threshold = float(crypto_settings.get("price_up_percent", 3.0) or 3.0)
        down_threshold = float(crypto_settings.get("price_down_percent", 3.0) or 3.0)
        for coin_id, payload in prices.items():
            prev_price = float(previous.get(coin_id, 0.0) or 0.0)
            current_price = float(payload.get("price", 0.0) or 0.0)
            if prev_price <= 0 or current_price <= 0:
                continue
            movement = crypto_movement_summary(prev_price, current_price)
            if movement >= up_threshold or movement <= -down_threshold:
                direction = "up" if movement >= 0 else "down"
                summary = f"{crypto_slug_to_name(coin_id)} moved {direction}"
                body = f"{movement:+.2f}% since the last check • {current_price:,.2f} {payload.get('currency', 'USD')}"
                url = f"https://www.coingecko.com/en/coins/{coin_id}"
                self._send_action_notification(summary, body, "Open", url, 23000 + abs(hash(coin_id)) % 500)
        state["last_prices"] = {coin_id: float(payload.get("price", 0.0) or 0.0) for coin_id, payload in prices.items()}
        state["last_checked_at"] = datetime.now().astimezone().isoformat()
        save_crypto_tracker_state(state)

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
        self._apply_icon_to_widget(self.net_icon, "wifi" if connected else "wifi_off", material_icon("wifi" if connected else "wifi_off"), 16)
        vpn_payload = {}
        raw = run_script("vpn.sh", "--status")
        if raw:
            try:
                vpn_payload = json.loads(raw)
            except Exception:
                vpn_payload = {}
        wg_active = vpn_payload.get("wireguard") == "on"
        selected_iface = str(vpn_payload.get("wg_selected", "")).strip()
        self._set_vpn_button_icon(wg_active)
        self.vpn_icon.setProperty("active", wg_active)
        self.vpn_icon.setToolTip(f"WireGuard: {selected_iface or 'No config selected'}")
        self.style().unpolish(self.vpn_icon)
        self.style().polish(self.vpn_icon)

    def _set_vpn_button_icon(self, active: bool) -> None:
        self._apply_icon_to_widget(self.vpn_icon, "vpn_key", material_icon("vpn_key"), 16)

    def _set_christian_button_icon(self) -> None:
        icon = tinted_svg_icon(CHRISTIAN_ICON, QColor(self.theme.primary), 16)
        if not icon.isNull():
            self.christian_button.setIcon(icon)
            self.christian_button.setText("")
            return
        self.christian_button.setIcon(QIcon())
        self.christian_button.setText(self._bar_icon_overrides.get("christian_widget", material_icon("auto_awesome")))
        self.christian_button.setFont(QFont(self.material_font, 16))

    def _sync_christian_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("christian_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", service.get("show_in_notification_center", False)))
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
        self.rss_button.setVisible(enabled and show_in_bar)

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

    def _sync_desktop_clock_process(self) -> None:
        service = self.service_settings.get("desktop_clock_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        target = desktop_clock_target()
        should_run = enabled and target is not None and not focused_workspace_has_real_windows()
        if not should_run:
            terminate_background_matches(str(DESKTOP_CLOCK_WIDGET))
            terminate_background_matches(str(DESKTOP_CLOCK_BINARY))
            if self._desktop_clock_process is not None and self._desktop_clock_process.poll() is None:
                self._desktop_clock_process.terminate()
            self._desktop_clock_process = None
            return
        if self._desktop_clock_process is not None and self._desktop_clock_process.poll() is None:
            return
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

    def _poll_lock_states(self) -> None:
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
        self._apply_icon_to_widget(self.caffeine_icon, "coffee", material_icon("coffee"), 16)

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
            self._control_center_process is not None and self._control_center_process.poll() is None
        ) or background_match_exists(str(NOTIFICATION_CENTER)) or background_match_exists(str(NOTIFICATION_CENTER_BINARY))
        if active:
            terminate_background_matches(str(NOTIFICATION_CENTER))
            terminate_background_matches(str(NOTIFICATION_CENTER_BINARY))
            try:
                subprocess.run(
                    ["pkill", "-x", "hanauta-notification-center"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
            if self._control_center_process is not None and self._control_center_process.poll() is None:
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
            terminate_background_matches(str(NOTIFICATION_CENTER))
            terminate_background_matches(str(NOTIFICATION_CENTER_BINARY))
            if NOTIFICATION_CENTER_BINARY.exists():
                self._control_center_process = subprocess.Popen(
                    [str(NOTIFICATION_CENTER_BINARY)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                python_bin = self._python_bin()
                self._control_center_process = subprocess.Popen(
                    [python_bin, str(NOTIFICATION_CENTER)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
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
        python_bin = ROOT / ".venv" / "bin" / "python"
        if python_bin.exists():
            return str(python_bin)
        return sys.executable

    def _singleton_active(self, process: Optional[subprocess.Popen], script_path: Path) -> bool:
        return (
            process is not None and process.poll() is None
        ) or background_match_exists(str(script_path))

    def _terminate_singleton_process(self, attr_name: str, script_path: Path) -> None:
        process = getattr(self, attr_name, None)
        if process is not None and process.poll() is None:
            process.terminate()
        terminate_background_matches(str(script_path))
        setattr(self, attr_name, None)

    def _launch_singleton_process(
        self,
        attr_name: str,
        script_path: Path,
        *,
        python_bin: Optional[str] = None,
    ) -> bool:
        if not script_path.exists():
            setattr(self, attr_name, None)
            return False
        self._terminate_singleton_process(attr_name, script_path)
        try:
            if python_bin is not None:
                command = [python_bin, str(script_path)]
            elif script_path.suffix == ".py":
                command = [widget_python(), str(script_path)]
            else:
                command = [str(script_path)]
            process = subprocess.Popen(
                command,
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
        script_path: Path,
        *,
        python_bin: Optional[str] = None,
    ) -> bool:
        if self._singleton_active(getattr(self, attr_name, None), script_path):
            self._terminate_singleton_process(attr_name, script_path)
            return False
        return self._launch_singleton_process(attr_name, script_path, python_bin=python_bin)

    def _toggle_weather_popup(self) -> None:
        self._toggle_singleton_process("_weather_popup_process", WEATHER_POPUP, python_bin=self._python_bin())

    def _toggle_calendar_popup(self) -> None:
        self._toggle_singleton_process("_calendar_popup_process", CALENDAR_POPUP, python_bin=self._python_bin())

    def _toggle_wifi_popup(self) -> None:
        active = self._toggle_singleton_process("_wifi_popup_process", WIFI_CONTROL, python_bin=self._python_bin())
        if not WIFI_CONTROL.exists():
            self.net_icon.setChecked(False)
            return
        self.net_icon.setChecked(active)

    def _toggle_vpn_popup(self) -> None:
        active = self._toggle_singleton_process("_vpn_popup_process", VPN_CONTROL, python_bin=self._python_bin())
        if not VPN_CONTROL.exists():
            self.vpn_icon.setChecked(False)
            return
        self.vpn_icon.setChecked(active)

    def _toggle_ai_popup(self) -> None:
        active = self._toggle_singleton_process("_ai_popup_process", AI_POPUP, python_bin=self._python_bin())
        if not AI_POPUP.exists():
            self.ai_button.setChecked(False)
            return
        self.ai_button.setChecked(active)

    def _open_region_settings(self) -> None:
        if not SETTINGS_PAGE.exists():
            return
        python_bin = self._python_bin()
        try:
            terminate_background_matches(str(SETTINGS_PAGE))
            subprocess.Popen(
                [python_bin, str(SETTINGS_PAGE), "--page", "region"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
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
        if not CHRISTIAN_WIDGET.exists():
            return
        self._toggle_singleton_process("_christian_widget_process", CHRISTIAN_WIDGET, python_bin=self._python_bin())

    def _open_reminders_widget(self) -> None:
        if not REMINDERS_WIDGET.exists():
            return
        self._toggle_singleton_process("_reminders_widget_process", REMINDERS_WIDGET, python_bin=self._python_bin())

    def _open_pomodoro_widget(self) -> None:
        if not POMODORO_WIDGET.exists():
            return
        self._toggle_singleton_process("_pomodoro_widget_process", POMODORO_WIDGET)

    def _open_rss_widget(self) -> None:
        if not RSS_WIDGET.exists():
            return
        self._toggle_singleton_process("_rss_widget_process", RSS_WIDGET)

    def _open_obs_widget(self) -> None:
        if not OBS_WIDGET.exists():
            return
        self._toggle_singleton_process("_obs_widget_process", OBS_WIDGET)

    def _open_crypto_widget(self) -> None:
        if not CRYPTO_WIDGET.exists():
            return
        self._toggle_singleton_process("_crypto_widget_process", CRYPTO_WIDGET)

    def _open_vps_widget(self) -> None:
        if not VPS_WIDGET.exists():
            return
        self._toggle_singleton_process("_vps_widget_process", VPS_WIDGET)

    def _toggle_ntfy_popup(self) -> None:
        if not NTFY_POPUP.exists():
            self.ntfy_button.setChecked(False)
            return
        active = self._toggle_singleton_process("_ntfy_popup_process", NTFY_POPUP, python_bin=self._python_bin())
        self.ntfy_button.setChecked(active)

    def _toggle_game_mode_popup(self) -> None:
        if not GAME_MODE_POPUP.exists():
            self.game_mode_button.setChecked(False)
            return
        active = self._toggle_singleton_process("_game_mode_popup_process", GAME_MODE_POPUP, python_bin=self._python_bin())
        self.game_mode_button.setChecked(active)

    def _open_launcher(self) -> None:
        if not LAUNCHER_APP.exists():
            return
        self._toggle_singleton_process("_launcher_process", LAUNCHER_APP, python_bin=self._python_bin())

    def _toggle_powermenu(self) -> None:
        if not POWERMENU_APP.exists():
            self.btn_power.setChecked(False)
            return
        active = self._toggle_singleton_process("_powermenu_process", POWERMENU_APP)
        self.btn_power.setChecked(active)

    def _open_clipboard(self) -> None:
        run_bg([str(ROOT / "scripts" / "openapps"), "--clip"])

    def _check_updates(self) -> None:
        run_bg([str(ROOT / "scripts" / "openapps"), "--checkupdates"])

    def _sync_ai_button(self) -> None:
        active = self._singleton_active(self._ai_popup_process, AI_POPUP)
        if not active:
            self._ai_popup_process = None
        self.ai_button.setChecked(active)

    def _sync_control_center_button(self) -> None:
        active = self._control_center_launch_pending or (
            self._control_center_process is not None and self._control_center_process.poll() is None
        ) or background_match_exists(str(NOTIFICATION_CENTER)) or background_match_exists(str(NOTIFICATION_CENTER_BINARY))
        if not active:
            self._control_center_process = None
        self.btn_control_center.setChecked(active)

    def _sync_wifi_button(self) -> None:
        active = self._singleton_active(self._wifi_popup_process, WIFI_CONTROL)
        if not active:
            self._wifi_popup_process = None
        self.net_icon.setChecked(active)

    def _sync_vpn_button(self) -> None:
        active = self._singleton_active(self._vpn_popup_process, VPN_CONTROL)
        if not active:
            self._vpn_popup_process = None
        self.vpn_icon.setChecked(active)

    def _sync_weather_button(self) -> None:
        active = self._singleton_active(self._weather_popup_process, WEATHER_POPUP)
        if not active:
            self._weather_popup_process = None

    def _sync_ntfy_button(self) -> None:
        active = self._singleton_active(self._ntfy_popup_process, NTFY_POPUP)
        if not active:
            self._ntfy_popup_process = None
        self.ntfy_button.setChecked(active)

    def _sync_game_mode_button(self) -> None:
        active = self._singleton_active(self._game_mode_popup_process, GAME_MODE_POPUP)
        if not active:
            self._game_mode_popup_process = None
        current = game_mode_summary()
        self.game_mode_button.setChecked(active)
        self.game_mode_button.setProperty("active", bool(current.get("active", False)))
        self.game_mode_button.setToolTip(str(current.get("note", "Game Mode")))
        self.style().unpolish(self.game_mode_button)
        self.style().polish(self.game_mode_button)

    def _sync_powermenu_button(self) -> None:
        active = self._singleton_active(self._powermenu_process, POWERMENU_APP)
        if not active:
            self._powermenu_process = None
        self.btn_power.setChecked(active)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._cava_process is not None:
            self._cava_process.kill()
            self._cava_process.waitForFinished(300)
        if self._ai_popup_process is not None and self._ai_popup_process.poll() is None:
            self._ai_popup_process.terminate()
        if self._control_center_process is not None and self._control_center_process.poll() is None:
            self._control_center_process.terminate()
        if self._wifi_popup_process is not None and self._wifi_popup_process.poll() is None:
            self._wifi_popup_process.terminate()
        if self._vpn_popup_process is not None and self._vpn_popup_process.poll() is None:
            self._vpn_popup_process.terminate()
        if self._weather_popup_process is not None and self._weather_popup_process.poll() is None:
            self._weather_popup_process.terminate()
        if self._christian_widget_process is not None and self._christian_widget_process.poll() is None:
            self._christian_widget_process.terminate()
        if self._pomodoro_widget_process is not None and self._pomodoro_widget_process.poll() is None:
            self._pomodoro_widget_process.terminate()
        if self._rss_widget_process is not None and self._rss_widget_process.poll() is None:
            self._rss_widget_process.terminate()
        if self._obs_widget_process is not None and self._obs_widget_process.poll() is None:
            self._obs_widget_process.terminate()
        if self._crypto_widget_process is not None and self._crypto_widget_process.poll() is None:
            self._crypto_widget_process.terminate()
        if self._vps_widget_process is not None and self._vps_widget_process.poll() is None:
            self._vps_widget_process.terminate()
        if self._desktop_clock_process is not None and self._desktop_clock_process.poll() is None:
            self._desktop_clock_process.terminate()
        if self._ntfy_popup_process is not None and self._ntfy_popup_process.poll() is None:
            self._ntfy_popup_process.terminate()
        if self._game_mode_popup_process is not None and self._game_mode_popup_process.poll() is None:
            self._game_mode_popup_process.terminate()
        if self._powermenu_process is not None and self._powermenu_process.poll() is None:
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
        QTimer.singleShot(150, self._apply_i3_window_rules)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_window_mask()

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)

    def _set_window_class(self) -> None:
        try:
            wid = int(self.winId())
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "_NET_WM_NAME", "8t", "-set", "_NET_WM_NAME", "CyberBar"],
                check=False,
            )
            subprocess.run(
                ["xprop", "-id", hex(wid), "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "CyberBar"],
                check=False,
            )
        except Exception:
            pass

    def _apply_i3_window_rules(self) -> None:
        try:
            subprocess.run(
                [
                    "i3-msg",
                    '[title="CyberBar"]',
                    "floating enable, sticky enable, move position 0 0",
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

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    app.setPalette(palette)

    bar = CyberBar()
    bar.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
