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

from PyQt6.QtCore import QByteArray, QEasingCurve, QObject, QPoint, QProcess, QPropertyAnimation, QSize, Qt, QTimer, pyqtClassInfo, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface
from PyQt6.QtGui import QColor, QCursor, QFont, QFontDatabase, QIcon, QPainter, QPalette, QPixmap, QRegion
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
if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.theme import load_theme_palette, palette_mtime

SCRIPTS_DIR = APP_DIR / "eww" / "scripts"
NOTIFICATION_CENTER = APP_DIR / "pyqt" / "notification-center" / "notification_center.py"
AI_POPUP = APP_DIR / "pyqt" / "ai-popup" / "ai_popup.py"
WIFI_CONTROL = APP_DIR / "pyqt" / "widget-wifi-control" / "wifi_control.py"
VPN_CONTROL = APP_DIR / "pyqt" / "widget-vpn-control" / "vpn_control.py"
CHRISTIAN_WIDGET = APP_DIR / "pyqt" / "widget-religion-christian" / "christian_widget.py"
LAUNCHER_APP = APP_DIR / "pyqt" / "launcher" / "launcher.py"
POWERMENU_APP = APP_DIR / "pyqt" / "powermenu" / "powermenu.py"
CAVA_BAR_CONFIG = APP_DIR / "pyqt" / "bar" / "cava_bar.conf"
FONTS_DIR = ROOT / "assets" / "fonts"
ASSETS_DIR = APP_DIR / "assets"
VPN_ICON_ON = ASSETS_DIR / "vpn_key.svg"
VPN_ICON_OFF = ASSETS_DIR / "vpn_key_off.svg"
CHRISTIAN_ICON = ASSETS_DIR / "cath.svg"
SETTINGS_FILE = Path.home() / ".local" / "state" / "hanauta" / "notification-center" / "settings.json"
TRAY_SLOT_WIDTH = 24
TRAY_SLOT_HEIGHT = 32
TRAY_SLOT_SIZE = 20
TRAY_ICON_SIZE = 16

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
    "pause": "\ue034",
    "play_arrow": "\ue037",
    "power_settings_new": "\ue8ac",
    "skip_next": "\ue044",
    "skip_previous": "\ue045",
    "system_update": "\ue62a",
    "shield": "\ue9e0",
    "trip_origin": "\ue57b",
    "vpn_key": "\ue0da",
    "wifi": "\ue63e",
    "wifi_off": "\ue648",
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


def detect_font(*families: str) -> str:
    for family in families:
        if QFont(family).exactMatch():
            return family
    return "Sans Serif"


def material_icon(name: str) -> str:
    return MATERIAL_ICONS.get(name, "?")


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_symbols_outlined": FONTS_DIR / "MaterialSymbolsOutlined.ttf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
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


class CyberBar(QWidget):
    def __init__(self, ui_path: Optional[Path] = None):
        super().__init__()
        self.ui_path = ui_path
        self.loaded_fonts = load_app_fonts()
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
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
        self.workspace_buttons: dict[int, WorkspaceDot] = {}
        self._media_animation: Optional[QPropertyAnimation] = None
        self._media_playing = False
        self._cava_process: Optional[QProcess] = None
        self._ai_popup_process: Optional[subprocess.Popen] = None
        self._control_center_process: Optional[subprocess.Popen] = None
        self._wifi_popup_process: Optional[subprocess.Popen] = None
        self._vpn_popup_process: Optional[subprocess.Popen] = None
        self._christian_widget_process: Optional[subprocess.Popen] = None
        self._powermenu_process: Optional[subprocess.Popen] = None
        self._cava_buffer = ""
        self._battery_base: Optional[Path] = self._detect_battery_base()
        self._setup_window()
        self._build_ui()
        self._apply_styles()
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
        self.setFixedSize(geo.width(), 40)
        self.move(geo.x(), geo.y())

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 4, 12, 4)
        root.setSpacing(14)

        left_wrap = QWidget()
        left_layout = QHBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.ai_button = self._icon_button("auto_awesome")
        self.ai_button.setObjectName("aiToggleButton")
        self.ai_button.setCheckable(True)
        self.ai_button.clicked.connect(self._toggle_ai_popup)
        left_layout.addWidget(self.ai_button)

        self.launcher_button = QPushButton("♪ hanauta")
        self.launcher_button.setObjectName("launcherButton")
        self.launcher_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.launcher_button.clicked.connect(self._open_launcher)
        left_layout.addWidget(self.launcher_button)

        self.workspace_chip = QFrame()
        self.workspace_chip.setObjectName("workspaceChip")
        workspace_layout = QHBoxLayout(self.workspace_chip)
        workspace_layout.setContentsMargins(12, 4, 12, 4)
        workspace_layout.setSpacing(8)

        self.workspace_label = QLabel("Workspace 1")
        self.workspace_label.setObjectName("workspaceLabel")
        workspace_layout.addWidget(self.workspace_label)

        dots_wrap = QWidget()
        dots_layout = QHBoxLayout(dots_wrap)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(6)
        for ws_num in range(1, 6):
            dot = WorkspaceDot(ws_num, self._goto_workspace)
            self.workspace_buttons[ws_num] = dot
            dots_layout.addWidget(dot)
        workspace_layout.addWidget(dots_wrap)
        left_layout.addWidget(self.workspace_chip)
        root.addWidget(left_wrap, 0, Qt.AlignmentFlag.AlignLeft)

        center_wrap = QWidget()
        center_layout = QHBoxLayout(center_wrap)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)

        self.datetime_chip = QFrame()
        self.datetime_chip.setObjectName("dateTimeChip")
        datetime_layout = QHBoxLayout(self.datetime_chip)
        datetime_layout.setContentsMargins(12, 4, 12, 4)
        datetime_layout.setSpacing(8)

        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("timeLabel")
        self.date_label = QLabel("--")
        self.date_label.setObjectName("dateLabel")
        datetime_layout.addWidget(self.time_label)
        datetime_layout.addWidget(self.date_label)
        self.btn_control_center = self._icon_button("dashboard")
        self.btn_control_center.setObjectName("utilityButton")
        self.btn_control_center.setCheckable(True)
        self.btn_control_center.clicked.connect(self._toggle_notifications)
        datetime_layout.addWidget(self.btn_control_center)
        center_layout.addWidget(self.datetime_chip)

        self.media_chip = QFrame()
        self.media_chip.setObjectName("mediaChip")
        self.media_chip.setProperty("active", False)
        self.media_opacity = QGraphicsOpacityEffect(self.media_chip)
        self.media_chip.setGraphicsEffect(self.media_opacity)
        self.media_opacity.setOpacity(0.0)
        media_layout = QHBoxLayout(self.media_chip)
        media_layout.setContentsMargins(14, 4, 14, 4)
        media_layout.setSpacing(8)

        self.media_icon = QLabel(material_icon("music_note"))
        self.media_icon.setObjectName("mediaIcon")
        self.media_icon.setFont(QFont(self.material_font, 16))
        self.media_equalizer = QWidget()
        self.media_equalizer.setObjectName("equalizerWrap")
        equalizer_layout = QHBoxLayout(self.media_equalizer)
        equalizer_layout.setContentsMargins(0, 0, 0, 0)
        equalizer_layout.setSpacing(3)
        self.equalizer_bars: list[EqualizerBar] = []
        for _ in range(6):
            bar = EqualizerBar()
            self.equalizer_bars.append(bar)
            equalizer_layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignBottom)
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

        media_layout.addWidget(self.media_icon)
        media_layout.addWidget(self.media_equalizer)
        media_layout.addWidget(self.media_text)
        media_layout.addWidget(self.media_prev)
        media_layout.addWidget(self.media_play)
        media_layout.addWidget(self.media_next)
        center_layout.addWidget(self.media_chip)
        root.addWidget(center_wrap, 1, Qt.AlignmentFlag.AlignCenter)

        right_wrap = QWidget()
        right_layout = QHBoxLayout(right_wrap)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.status_chip = QFrame()
        self.status_chip.setObjectName("statusChip")
        status_layout = QHBoxLayout(self.status_chip)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(8)

        self.net_icon = QPushButton(material_icon("wifi"))
        self.net_icon.setObjectName("statusIconButton")
        self.net_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.net_icon.setCheckable(True)
        self.net_icon.clicked.connect(self._toggle_wifi_popup)
        self.vpn_icon = QPushButton("")
        self.vpn_icon.setObjectName("statusIconButton")
        self.vpn_icon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.vpn_icon.setCheckable(True)
        self.vpn_icon.setText(material_icon("vpn_key"))
        self.vpn_icon.clicked.connect(self._toggle_vpn_popup)
        self.christian_button = QPushButton("")
        self.christian_button.setObjectName("statusIconButton")
        self.christian_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.christian_button.clicked.connect(self._open_christian_widget)
        self.christian_button.setIconSize(QSize(16, 16))
        self.battery_icon = QLabel(material_icon("battery_full"))
        self.battery_icon.setObjectName("statusIcon")
        self.caffeine_icon = QLabel(material_icon("coffee"))
        self.caffeine_icon.setObjectName("statusIcon")
        self.battery_value = QLabel("100")
        self.battery_value.setObjectName("batteryValue")
        for label in (self.net_icon, self.vpn_icon, self.battery_icon, self.caffeine_icon):
            label.setFont(QFont(self.material_font, 16))
        status_layout.addWidget(self.net_icon)
        status_layout.addWidget(self.vpn_icon)
        status_layout.addWidget(self.christian_button)
        status_layout.addWidget(self.caffeine_icon)
        status_layout.addWidget(self.battery_icon)
        status_layout.addWidget(self.battery_value)
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
        status_layout.addWidget(self.btn_clip)
        status_layout.addWidget(self.btn_updates)
        status_layout.addWidget(self.tray_host)
        status_layout.addWidget(self.btn_power)
        right_layout.addWidget(self.status_chip)
        root.addWidget(right_wrap, 0, Qt.AlignmentFlag.AlignRight)

        has_battery = self._battery_base is not None
        self.caffeine_icon.setVisible(False)
        self.battery_icon.setVisible(has_battery)
        self.battery_value.setVisible(has_battery)
        self._set_vpn_button_icon(False)
        self._set_christian_button_icon()
        self._sync_christian_button_visibility()
        self._install_debug_tooltips()

    def _icon_button(self, icon_name: str) -> QPushButton:
        button = QPushButton(material_icon(icon_name))
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        button.setFont(QFont(self.material_font, 18))
        button.setToolTip(f"IconButton {icon_name}")
        return button

    def _install_debug_tooltips(self) -> None:
        self.setToolTip("CyberBar root")
        self.ai_button.setToolTip("AI toggle button")
        self.launcher_button.setToolTip("Launcher button")
        self.workspace_chip.setToolTip("Workspace chip")
        self.workspace_label.setToolTip("Workspace label")
        self.datetime_chip.setToolTip("Date/time chip")
        self.time_label.setToolTip("Time label")
        self.date_label.setToolTip("Date label")
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
        self.caffeine_icon.setToolTip("Caffeine icon")
        self.battery_icon.setToolTip("Battery icon")
        self.battery_value.setToolTip("Battery value")
        self.btn_clip.setToolTip("Clipboard button")
        self.btn_updates.setToolTip("Updates button")
        self.tray_host.setToolTip("Qt StatusNotifier tray")
        self.btn_power.setToolTip("Power button")

    def _apply_styles(self) -> None:
        theme = self.theme
        status_icon_color = theme.primary
        status_hover_color = theme.text
        status_active_color = theme.primary
        self.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                color: {theme.text};
                font-family: "Inter", "Noto Sans", sans-serif;
                font-size: 12px;
            }}
            #workspaceChip, #dateTimeChip {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
                border-radius: 16px;
            }}
            #mediaChip {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 16px;
            }}
            #mediaChip[active="false"] {{
                background: {theme.chip_bg};
                border: 1px solid {theme.chip_border};
            }}
            #statusChip {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 16px;
            }}
            #launcherButton {{
                background: {theme.hover_bg};
                border: 1px solid {theme.app_focused_border};
                border-radius: 16px;
                color: {theme.primary};
                font-weight: 700;
                padding: 0 12px;
                min-height: 30px;
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
                border-radius: 11px;
            }}
            #statusIconButton:checked {{
                color: {status_active_color};
                background: {theme.accent_soft};
                border-radius: 11px;
            }}
            #statusIconButton[active="true"] {{
                color: {status_active_color};
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
            #mediaControl:hover, #utilityButton:hover, #launcherButton:hover, #aiToggleButton:hover {{
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
            #aiToggleButton:checked {{
                color: {theme.primary};
                background: {theme.accent_soft};
                border-radius: 11px;
            }}
            #timeLabel {{
                color: {theme.text};
                font-size: 12px;
                font-weight: 700;
                padding-right: 2px;
            }}
            #dateLabel {{
                color: {theme.text_muted};
                font-size: 11px;
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
        self._update_window_mask()

    def _update_media_equalizer_color(self) -> None:
        color = self.theme.equalizer if self._media_playing else self.theme.text_muted
        for bar in getattr(self, "equalizer_bars", []):
            bar.set_color(color)

    def _reload_theme_if_needed(self) -> None:
        current_mtime = palette_mtime()
        if current_mtime == self._theme_mtime:
            return
        self._theme_mtime = current_mtime
        self.theme = load_theme_palette()
        self._apply_styles()

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

        self.powermenu_timer = QTimer(self)
        self.powermenu_timer.timeout.connect(self._sync_powermenu_button)
        self.powermenu_timer.start(1000)

        self._start_cava()

    def _poll_all(self) -> None:
        self._poll_clock()
        self._poll_workspaces()
        self._poll_media()
        self._poll_system()

    def _poll_clock(self) -> None:
        now = datetime.now()
        self.time_label.setText(now.strftime("%-I:%M %p"))
        self.date_label.setText(now.strftime("%a, %m/%d"))

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
        self._sync_christian_button_visibility()

    def _poll_network(self) -> None:
        connected = run_script("network.sh", "status") == "Connected"
        self.net_icon.setText(material_icon("wifi" if connected else "wifi_off"))
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
        self.vpn_icon.setIcon(QIcon())
        self.vpn_icon.setText(material_icon("vpn_key"))

    def _set_christian_button_icon(self) -> None:
        icon = tinted_svg_icon(CHRISTIAN_ICON, QColor(self.theme.primary), 16)
        if not icon.isNull():
            self.christian_button.setIcon(icon)
            self.christian_button.setText("")
            return
        self.christian_button.setIcon(QIcon())
        self.christian_button.setText(material_icon("auto_awesome"))
        self.christian_button.setFont(QFont(self.material_font, 16))

    def _sync_christian_button_visibility(self) -> None:
        services = load_service_settings()
        service = services.get("christian_widget", {})
        if not isinstance(service, dict):
            service = {}
        enabled = bool(service.get("enabled", True))
        show_in_bar = bool(service.get("show_in_bar", service.get("show_in_notification_center", False)))
        self.christian_button.setVisible(enabled and show_in_bar)

    def _poll_caffeine(self) -> None:
        caffeine_on = run_script("caffeine.sh", "status") == "on"
        self.caffeine_icon.setVisible(caffeine_on)

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

        self.battery_icon.setText(material_icon(icon))
        self.battery_value.setText(str(capacity))
        self.battery_icon.show()
        self.battery_value.show()

    def _goto_workspace(self, num: int) -> None:
        run_cmd(["i3-msg", "workspace", str(num)])
        self._poll_workspaces()

    def _toggle_notifications(self) -> None:
        if self._control_center_process is not None and self._control_center_process.poll() is None:
            self._control_center_process.terminate()
            self._control_center_process = None
            self.btn_control_center.setChecked(False)
            return

        if not NOTIFICATION_CENTER.exists():
            self.btn_control_center.setChecked(False)
            return

        try:
            self._control_center_process = subprocess.Popen(
                [sys.executable, str(NOTIFICATION_CENTER)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.btn_control_center.setChecked(True)
        except Exception:
            self._control_center_process = None
            self.btn_control_center.setChecked(False)

    def _toggle_wifi_popup(self) -> None:
        if self._wifi_popup_process is not None and self._wifi_popup_process.poll() is None:
            self._wifi_popup_process.terminate()
            self._wifi_popup_process = None
            self.net_icon.setChecked(False)
            return

        if not WIFI_CONTROL.exists():
            self.net_icon.setChecked(False)
            return

        python_bin = ROOT / ".venv" / "bin" / "python"
        try:
            self._wifi_popup_process = subprocess.Popen(
                [str(python_bin), str(WIFI_CONTROL)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.net_icon.setChecked(True)
        except Exception:
            self._wifi_popup_process = None
            self.net_icon.setChecked(False)

    def _toggle_vpn_popup(self) -> None:
        if self._vpn_popup_process is not None and self._vpn_popup_process.poll() is None:
            self._vpn_popup_process.terminate()
            self._vpn_popup_process = None
            self.vpn_icon.setChecked(False)
            return

        if not VPN_CONTROL.exists():
            self.vpn_icon.setChecked(False)
            return

        python_bin = ROOT / ".venv" / "bin" / "python"
        try:
            self._vpn_popup_process = subprocess.Popen(
                [str(python_bin), str(VPN_CONTROL)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.vpn_icon.setChecked(True)
        except Exception:
            self._vpn_popup_process = None
            self.vpn_icon.setChecked(False)

    def _toggle_ai_popup(self) -> None:
        if self._ai_popup_process is not None and self._ai_popup_process.poll() is None:
            self._ai_popup_process.terminate()
            self._ai_popup_process = None
            self.ai_button.setChecked(False)
            return

        if not AI_POPUP.exists():
            self.ai_button.setChecked(False)
            return

        python_bin = ROOT / ".venv" / "bin" / "python"
        try:
            self._ai_popup_process = subprocess.Popen(
                [str(python_bin), str(AI_POPUP)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.ai_button.setChecked(True)
        except Exception:
            self._ai_popup_process = None
            self.ai_button.setChecked(False)

    def _open_christian_widget(self) -> None:
        if not CHRISTIAN_WIDGET.exists():
            return
        if self._christian_widget_process is not None and self._christian_widget_process.poll() is None:
            self._christian_widget_process.terminate()
            self._christian_widget_process = None
            return

        python_bin = ROOT / ".venv" / "bin" / "python"
        try:
            self._christian_widget_process = subprocess.Popen(
                [str(python_bin), str(CHRISTIAN_WIDGET)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self._christian_widget_process = None

    def _open_launcher(self) -> None:
        python_bin = ROOT / ".venv" / "bin" / "python"
        if LAUNCHER_APP.exists():
            run_bg([str(python_bin), str(LAUNCHER_APP)])

    def _toggle_powermenu(self) -> None:
        if self._powermenu_process is not None and self._powermenu_process.poll() is None:
            self._powermenu_process.terminate()
            self._powermenu_process = None
            self.btn_power.setChecked(False)
            return

        if not POWERMENU_APP.exists():
            self.btn_power.setChecked(False)
            return

        python_bin = ROOT / ".venv" / "bin" / "python"
        try:
            self._powermenu_process = subprocess.Popen(
                [str(python_bin), str(POWERMENU_APP)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.btn_power.setChecked(True)
        except Exception:
            self._powermenu_process = None
            self.btn_power.setChecked(False)

    def _open_clipboard(self) -> None:
        run_bg([str(ROOT / "scripts" / "openapps"), "--clip"])

    def _check_updates(self) -> None:
        run_bg([str(ROOT / "scripts" / "openapps"), "--checkupdates"])

    def _sync_ai_button(self) -> None:
        active = self._ai_popup_process is not None and self._ai_popup_process.poll() is None
        if not active:
            self._ai_popup_process = None
        self.ai_button.setChecked(active)

    def _sync_control_center_button(self) -> None:
        active = self._control_center_process is not None and self._control_center_process.poll() is None
        if not active:
            self._control_center_process = None
        self.btn_control_center.setChecked(active)

    def _sync_wifi_button(self) -> None:
        active = self._wifi_popup_process is not None and self._wifi_popup_process.poll() is None
        if not active:
            self._wifi_popup_process = None
        self.net_icon.setChecked(active)

    def _sync_vpn_button(self) -> None:
        active = self._vpn_popup_process is not None and self._vpn_popup_process.poll() is None
        if not active:
            self._vpn_popup_process = None
        self.vpn_icon.setChecked(active)

    def _sync_powermenu_button(self) -> None:
        active = self._powermenu_process is not None and self._powermenu_process.poll() is None
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
        if self._christian_widget_process is not None and self._christian_widget_process.poll() is None:
            self._christian_widget_process.terminate()
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
